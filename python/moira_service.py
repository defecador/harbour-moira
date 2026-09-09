#!/usr/bin/env python3
"""Moira extraction service.

Loaded in-process by pyotherside, which runs it on its own thread and
marshals values to and from QML. QML calls exactly one entry point:

    moira_service.call("search", {"query": "cats", "limit": 20})
    -> {"ok": True, "result": {"items": [...]}}
    -> {"ok": False, "error": "..."}

A subprocess would be simpler to reason about, but Sailjail launches every
app with firejail's --private-bin, leaving just the app binary in /usr/bin -
there is no python3 to spawn. Embedding the interpreter sidesteps that
entirely.

Running this file directly still starts a line-based JSON loop on stdin,
which is how the extraction paths get tested off-device.
"""

import hashlib
import io
import json
import os
import re
import sys
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

# Prefer a vendored yt-dlp so the app does not depend on the user running pip.
# Both layouts are supported: an unpacked directory, or the upstream zipapp
# (which Python can import from directly, and which is far smaller to ship).
_VENDOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
if os.path.isdir(_VENDOR):
    _ZIPAPP = os.path.join(_VENDOR, "yt-dlp.zip")
    if os.path.isfile(_ZIPAPP):
        sys.path.insert(0, _ZIPAPP)
    sys.path.insert(0, _VENDOR)

_UPDATE_DIR = os.path.join(
    os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"),
    "harbour-moira")
_UPDATE_ZIP = os.path.join(_UPDATE_DIR, "yt-dlp.zip")
if os.path.isfile(_UPDATE_ZIP):
    # Inserted last, so it lands ahead of the bundled copy.
    sys.path.insert(0, _UPDATE_ZIP)

try:
    from yt_dlp import YoutubeDL
    from yt_dlp.version import __version__ as YTDLP_VERSION
except ImportError as exc:  # Surfaced to the UI rather than crashing at startup.
    YoutubeDL = None
    YTDLP_VERSION = None
    _IMPORT_ERROR = str(exc)
else:
    _IMPORT_ERROR = None

_USER_AGENT = "Mozilla/5.0"

# YouTube retired the Trending feed, and public Invidious instances that used
# to expose /api/v1/popular are gone, so there is no feed to read any more.
# The closest honest substitute is its own search: most-viewed, uploaded this
# week. A single query is not enough - the seed term skews results hard
# (searching "e" returns a different language's content than "a"), so several
# deliberately broad seeds are merged and re-sorted by view count.
_POPULAR_SP = "CAMSBAgDEAE%3D"  # sort=view count, uploaded=this week
_POPULAR_SEEDS = ("a", "e", "i", "o", "the")

_RELEASE_API = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
_RELEASE_FILE = "https://github.com/yt-dlp/yt-dlp/releases/download/%s/%s"

_NO_FORMAT_MESSAGE = (
    "no playable format returned - this usually means YouTube withheld "
    "formats for lack of a PO token"
)

BASE_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "noprogress": True,
    "skip_download": True,
    "cachedir": os.path.join(
        os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")),
        "harbour-moira",
    ),
}


def _cache_dir():
    path = BASE_OPTS["cachedir"]
    os.makedirs(path, exist_ok=True)
    return path


def _fetch_master(url):
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def _variant_heights(body):
    return sorted({int(m) for m in re.findall(r"RESOLUTION=\d+x(\d+)", body)})


def _playable_heights(body):
    """Heights the device can actually decode - what the UI may offer.

    Anything vp09-only is excluded, so the quality menu never lists a
    resolution that fails on selection.
    """
    avc = sorted({
        int(re.search(r"RESOLUTION=\d+x(\d+)", line).group(1))
        for line in body.splitlines()
        if line.startswith("#EXT-X-STREAM-INF") and "avc1" in line
        and re.search(r"RESOLUTION=\d+x(\d+)", line)
    })
    return avc or _variant_heights(body)


def _original_audio_language(info):
    """The language the video was actually made in, per yt-dlp.

    YouTube auto-dubs a lot of popular content into 20+ languages. yt-dlp
    scores the original track language_preference 10 and every dub -1, which
    is more reliable than reading the "- dubbed" suffix out of a track name.
    """
    for fmt in info.get("formats") or []:
        if (fmt.get("language_preference") == 10
                and fmt.get("vcodec") in (None, "none")
                and fmt.get("language")):
            return fmt["language"]
    return None


def _filter_master(body, max_height, exact=False, audio_language=None):
    """Rewrite the master playlist down to the variants we want served.

    Quality has to be constrained here because GStreamer's adaptivedemux picks
    a variant by bandwidth on its own, and QtMultimedia 5.6 exposes no way to
    reach in and cap it. Rewriting the master is the only lever available.

    `exact` is what makes a chosen quality mean that quality. Left adaptive,
    the demuxer is handed every variant from 144p up, starts on the lowest one
    listed and climbs only as fast as it measures bandwidth - so picking
    "1080p" produced a 240p picture under a 1080p label. An explicit choice
    therefore serves one height and nothing else.

    Variants reference audio by group, so at least one rendition per group
    must survive or the stream is silenced. `audio_language` narrows each
    group to the original-language track: YouTube lists every dub with
    DEFAULT=NO and puts the original last, so a player with nothing to go on
    picks whichever dub comes first.
    """
    lines = body.splitlines()

    # YouTube offers avc1 and vp09 at most heights, and only vp09 above 1080p.
    # Measured on a MediaTek Jolla Phone: avc1 plays, vp09 at 1440p and 2160p
    # fails about half a second in. droidvdec does advertise video/x-vp9, so
    # this is a limit on high-resolution vp09 rather than the codec itself.
    # Whenever avc1 exists at all, it is the only thing served.
    avc_heights = set()
    for line in lines:
        if line.startswith("#EXT-X-STREAM-INF") and "avc1" in line:
            found = re.search(r"RESOLUTION=\d+x(\d+)", line)
            if found:
                avc_heights.add(int(found.group(1)))

    out = []
    kept = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("#EXT-X-MEDIA") and "TYPE=AUDIO" in line:
            found = re.search(r'LANGUAGE="([^"]*)"', line)
            language = found.group(1) if found else ""
            if audio_language and language and language != audio_language:
                index += 1
                continue  # a dub - drop it
            if audio_language and language == audio_language:
                # Nothing else is left in the group, so say so explicitly.
                line = line.replace("DEFAULT=NO", "DEFAULT=YES")
                line = line.replace("AUTOSELECT=NO", "AUTOSELECT=YES")
            out.append(line)
            index += 1
            continue
        if line.startswith("#EXT-X-STREAM-INF"):
            uri = lines[index + 1] if index + 1 < len(lines) else ""
            found = re.search(r"RESOLUTION=\d+x(\d+)", line)
            height = int(found.group(1)) if found else 0
            redundant = "avc1" not in line and bool(avc_heights)
            wanted = (height == max_height) if exact else (height <= max_height)
            if wanted and not redundant:
                out.extend((line, uri))
                kept.append(height)
            index += 2
            continue
        out.append(line)
        index += 1
    return "\n".join(out) + "\n", kept


def _capped_manifest(master_url, max_height, audio_language=None):
    """Write a filtered local manifest and return its path.

    The file deliberately avoids an .m3u8 suffix: Qt would recognise that as
    one of its own playlist formats and parse it instead of handing it to
    GStreamer, which typefinds on the #EXTM3U content regardless.
    """
    body = _fetch_master(master_url)
    heights = _playable_heights(body)
    if not heights:
        return None, []

    # The unfiltered master is never served: left to itself adaptivedemux
    # climbs by bandwidth into the vp09 variants, which fail on this hardware
    # a moment after playback starts.
    ceiling = max_height or heights[-1]
    filtered, kept = _filter_master(body, ceiling, exact=max_height > 0,
                                    audio_language=audio_language)
    if not kept and max_height > 0:
        # That exact height is not on offer; take everything up to it so the
        # viewer still gets the closest thing rather than nothing.
        filtered, kept = _filter_master(body, ceiling,
                                        audio_language=audio_language)
    if not kept:
        # Nothing matched - fall back to the smallest variant of any codec.
        filtered, kept = _filter_master(body, heights[0],
                                        audio_language=audio_language)

    # The filename must vary per stream. QMediaPlayer treats assigning an
    # unchanged source as a no-op, so a fixed path would leave the previous
    # video playing - or fail - on the next capped request.
    token = hashlib.sha1(
        ("%s|%d|%s" % (master_url, max_height, audio_language or "")
         ).encode("utf-8")).hexdigest()[:12]
    path = os.path.join(_cache_dir(), "manifest-%s.hls" % token)
    with open(path, "w") as handle:
        handle.write(filtered)
    _prune_manifests(keep=path)
    return path, heights


def _prune_manifests(keep, limit=4):
    """Drop stale manifests; their signed URLs expire within hours anyway."""
    try:
        directory = _cache_dir()
        entries = [
            os.path.join(directory, n) for n in os.listdir(directory)
            if n.startswith("manifest-") and n.endswith(".hls")
        ]
        entries = [e for e in entries if e != keep]
        entries.sort(key=os.path.getmtime, reverse=True)
        for stale in entries[limit:]:
            os.unlink(stale)
    except OSError:
        pass  # Housekeeping only; never fail a playback over it.


def _pick_thumbnail(entry):
    """Choose a mid-sized thumbnail; phone lists do not need maxres."""
    thumbs = entry.get("thumbnails") or []
    usable = [t for t in thumbs if t.get("url")]
    if not usable:
        return entry.get("thumbnail") or ""
    with_width = [t for t in usable if t.get("width")]
    if not with_width:
        return usable[-1]["url"]
    # Smallest thumbnail at least 320px wide, else the largest available.
    candidates = sorted(with_width, key=lambda t: t["width"])
    for thumb in candidates:
        if thumb["width"] >= 320:
            return thumb["url"]
    return candidates[-1]["url"]


def _as_result(entry):
    """Normalise a yt-dlp entry into the shape the QML models expect."""
    return {
        "videoId": entry.get("id") or "",
        "title": entry.get("title") or "",
        "uploader": entry.get("uploader") or entry.get("channel") or "",
        "uploaderId": entry.get("channel_id") or entry.get("uploader_id") or "",
        "duration": int(entry.get("duration") or 0),
        "thumbnail": _pick_thumbnail(entry),
        "viewCount": int(entry.get("view_count") or 0),
        "url": entry.get("webpage_url") or entry.get("url") or "",
        "live": bool(entry.get("is_live")),
    }


def _hls_master_url(info):
    """Find the master HLS playlist, which carries every variant plus audio.

    yt-dlp exposes it top level on some extractors, but for YouTube it only
    appears as `manifest_url` on the individual m3u8 formats - all of which
    point at the same master.
    """
    master = info.get("hls_manifest_url") or info.get("manifest_url")
    if master:
        return master
    for fmt in info.get("formats") or []:
        if "m3u8" in (fmt.get("protocol") or "") and fmt.get("manifest_url"):
            return fmt["manifest_url"]
    return None


def _normalise_url(params):
    """Accept either a full URL or a bare video id."""
    url = (params.get("url") or "").strip()
    if url:
        return url
    video_id = (params.get("id") or "").strip()
    if video_id:
        return "https://www.youtube.com/watch?v=%s" % video_id
    raise ValueError("either 'url' or 'id' is required")


# --- methods ---------------------------------------------------------------

def method_ping(_params):
    return {
        "ytdlp": YTDLP_VERSION,
        "python": sys.version.split()[0],
        # False means nothing can be extracted until an update is fetched.
        "available": YoutubeDL is not None,
        "vendored": os.path.isfile(_ZIPAPP) if os.path.isdir(_VENDOR) else False,
    }


def method_search(params):
    query = (params.get("query") or "").strip()
    if not query:
        raise ValueError("'query' is required")
    limit = max(1, min(int(params.get("limit") or 20), 50))

    opts = dict(BASE_OPTS)
    # Flat extraction: one request for the whole page instead of one per video.
    opts["extract_flat"] = "in_playlist"

    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info("ytsearch%d:%s" % (limit, query), download=False)

    entries = info.get("entries") or []
    return {"items": [_as_result(e) for e in entries if e]}


def method_video(params):
    url = _normalise_url(params)
    opts = dict(BASE_OPTS)

    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    result = _as_result(info)
    result.update({
        "description": info.get("description") or "",
        "uploadDate": info.get("upload_date") or "",
        "likeCount": int(info.get("like_count") or 0),
        "subscriberCount": int(info.get("channel_follower_count") or 0),
    })
    return result


def method_stream(params):
    """Resolve a directly playable URL.

    Video mode hands back YouTube's *master* HLS manifest rather than a single
    format. QtMultimedia 5.6 cannot merge separate audio and video streams
    itself, and YouTube no longer offers muxed progressive formats at all -
    but the master playlist carries audio renditions in EXT-X-MEDIA groups,
    which GStreamer's hlsdemux combines on its own. Its variants are also
    avc1/mp4a, so decoding stays on the hardware path.

    Audio mode stays on a plain progressive URL: one adaptive audio stream
    needs no muxing, and skipping HLS keeps background playback cheap.
    """
    url = _normalise_url(params)
    mode = (params.get("mode") or "video").lower()

    opts = dict(BASE_OPTS)
    if mode == "audio":
        opts["format"] = "bestaudio[ext=m4a]/bestaudio"

    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if mode == "audio":
        requested = info.get("requested_downloads") or []
        chosen = requested[0] if requested else info
        stream_url = chosen.get("url")
        if not stream_url:
            raise RuntimeError(_NO_FORMAT_MESSAGE)
        return {
            "url": stream_url,
            "mode": mode,
            "adaptive": False,
            "format_id": chosen.get("format_id") or "",
            "ext": chosen.get("ext") or "",
            "height": 0,
            "abr": float(chosen.get("abr") or 0),
            "duration": int(info.get("duration") or 0),
            "title": info.get("title") or "",
            "http_headers": chosen.get("http_headers") or {},
        }

    manifest = _hls_master_url(info)
    if manifest:
        max_height = int(params.get("max_height") or 0)
        url, heights = manifest, []
        try:
            capped, heights = _capped_manifest(
                manifest, max_height, _original_audio_language(info))
            if capped:
                url = "file://" + capped
        except Exception:
            # A capped manifest is a convenience; never lose playback over it.
            pass
        return {
            "url": url,
            "mode": "video",
            "adaptive": True,
            "format_id": "hls-adaptive" if max_height == 0 else "hls-capped",
            "ext": "m3u8",
            # 0 means the demuxer still chooses freely below the cap.
            "height": 0,
            "maxHeight": max_height,
            "qualities": list(reversed(heights)),
            "abr": 0.0,
            "duration": int(info.get("duration") or 0),
            "title": info.get("title") or "",
            "http_headers": info.get("http_headers") or {},
        }

    # No HLS: fall back to a muxed progressive format if one still exists.
    muxed = [
        f for f in (info.get("formats") or [])
        if f.get("vcodec") not in (None, "none")
        and f.get("acodec") not in (None, "none")
        and f.get("url")
    ]
    if not muxed:
        raise RuntimeError(_NO_FORMAT_MESSAGE)

    max_height = int(params.get("max_height") or 720)
    within = [f for f in muxed if (f.get("height") or 0) <= max_height]
    chosen = max(within or muxed, key=lambda f: f.get("height") or 0)

    return {
        "url": chosen["url"],
        "mode": "video",
        "adaptive": False,
        "format_id": chosen.get("format_id") or "",
        "ext": chosen.get("ext") or "",
        "height": int(chosen.get("height") or 0),
        "abr": float(chosen.get("abr") or 0),
        "duration": int(info.get("duration") or 0),
        "title": info.get("title") or "",
        "http_headers": chosen.get("http_headers") or {},
    }


def method_channel(params):
    url = (params.get("url") or "").strip()
    if not url:
        channel_id = (params.get("id") or "").strip()
        if not channel_id:
            raise ValueError("either 'url' or 'id' is required")
        url = "https://www.youtube.com/channel/%s/videos" % channel_id

    limit = max(1, min(int(params.get("limit") or 30), 100))
    opts = dict(BASE_OPTS)
    opts["extract_flat"] = "in_playlist"
    opts["playlistend"] = limit

    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    entries = info.get("entries") or []
    return {
        "title": info.get("title") or "",
        "id": info.get("channel_id") or info.get("id") or "",
        "items": [_as_result(e) for e in entries if e],
    }


def _http_get(url, timeout=60):
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _latest_release():
    return json.loads(_http_get(_RELEASE_API).decode("utf-8")).get("tag_name") or ""


def method_update_check(_params):
    latest = _latest_release()
    return {
        "current": YTDLP_VERSION or "",
        "latest": latest,
        "updateAvailable": bool(latest and latest != YTDLP_VERSION),
        "source": "downloaded" if os.path.isfile(_UPDATE_ZIP) else "bundled",
    }


def method_update_install(params):
    """Download a newer yt-dlp into the app's data directory.

    The package ships a working baseline, but YouTube breaks extraction on a
    timescale of weeks while releases happen on a timescale of months. This
    lets a user repair their own install, and keeps the dependency out of the
    build - OBS workers have no network access, so Chum could not fetch it.

    The payload is checked against the SHA2-256SUMS published with the same
    release. Both come from GitHub over TLS, so this guards against truncated
    or corrupted downloads rather than against GitHub itself; the release is
    also signed, and verifying that would need a trusted key shipped with the
    app.
    """
    version = (params.get("version") or "").strip() or _latest_release()
    if not version:
        raise RuntimeError("could not determine the latest yt-dlp release")

    sums = _http_get(_RELEASE_FILE % (version, "SHA2-256SUMS")).decode("utf-8", "replace")
    expected = ""
    for line in sums.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == "yt-dlp":
            expected = parts[0].lower()
            break
    if not expected:
        raise RuntimeError("release %s publishes no checksum for the zipapp" % version)

    payload = _http_get(_RELEASE_FILE % (version, "yt-dlp"), timeout=180)
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        raise RuntimeError(
            "checksum mismatch, refusing to install (expected %s..., got %s...)"
            % (expected[:16], actual[:16]))
    if not zipfile.is_zipfile(io.BytesIO(payload)):
        raise RuntimeError("downloaded file is not a zipapp")

    os.makedirs(_UPDATE_DIR, exist_ok=True)
    partial = _UPDATE_ZIP + ".part"
    with open(partial, "wb") as handle:
        handle.write(payload)
    os.replace(partial, _UPDATE_ZIP)  # Atomic: never leave a half-written zip.

    # If nothing was importable before - a package built without the vendored
    # zipapp, as OBS must produce - the interpreter holds no stale module tree
    # and the download can be used immediately. Only a genuine upgrade needs a
    # restart, because Python cannot unload the yt_dlp already in memory.
    global YoutubeDL, YTDLP_VERSION, _IMPORT_ERROR
    restart_required = True
    if YoutubeDL is None:
        if _UPDATE_ZIP not in sys.path:
            sys.path.insert(0, _UPDATE_ZIP)
        try:
            from yt_dlp import YoutubeDL as _YoutubeDL
            from yt_dlp.version import __version__ as _version
        except ImportError as exc:
            _IMPORT_ERROR = str(exc)
        else:
            YoutubeDL = _YoutubeDL
            YTDLP_VERSION = _version
            _IMPORT_ERROR = None
            restart_required = False

    return {
        "installed": version,
        "bytes": len(payload),
        "restartRequired": restart_required,
    }


def method_popular(params):
    limit = max(1, min(int(params.get("limit") or 20), 50))
    per_seed = max(4, limit // 2)

    def fetch(seed):
        opts = dict(BASE_OPTS)
        opts["extract_flat"] = "in_playlist"
        opts["playlistend"] = per_seed
        opts["ignoreerrors"] = True
        url = "https://www.youtube.com/results?search_query=%s&sp=%s" % (
            seed, _POPULAR_SP)
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            return [e for e in (info.get("entries") or []) if e]
        except Exception:
            return []  # One dead seed must not empty the whole screen.

    with ThreadPoolExecutor(max_workers=len(_POPULAR_SEEDS)) as pool:
        batches = list(pool.map(fetch, _POPULAR_SEEDS))

    merged = {}
    for entry in (e for batch in batches for e in batch):
        item = _as_result(entry)
        if item["videoId"] and item["videoId"] not in merged:
            merged[item["videoId"]] = item

    items = sorted(merged.values(), key=lambda i: i["viewCount"], reverse=True)
    return {"items": items[:limit]}


# These must stay reachable when yt-dlp is missing: they are how it arrives.
# A package built on OBS ships without the vendored zipapp, so the very first
# call on a fresh install is update_install.
_NEEDS_NO_EXTRACTOR = frozenset(("ping", "update_check", "update_install"))

METHODS = {
    "ping": method_ping,
    "popular": method_popular,
    "update_check": method_update_check,
    "update_install": method_update_install,
    "search": method_search,
    "video": method_video,
    "stream": method_stream,
    "channel": method_channel,
}


def call(method, params=None):
    """Single entry point for QML.

    Errors come back in the return value rather than as exceptions: a Python
    traceback crossing into pyotherside would surface on its global `error`
    signal with no way to tell which call produced it.
    """
    try:
        handler = METHODS.get(method)
        if handler is None:
            raise ValueError("unknown method '%s'" % method)
        if YoutubeDL is None and method not in _NEEDS_NO_EXTRACTOR:
            raise RuntimeError("yt-dlp is not available: %s" % _IMPORT_ERROR)
        return {"ok": True, "result": handler(params or {})}
    except Exception as exc:
        return {"ok": False, "error": "%s" % exc}


def main():
    """Line-based JSON on stdin/stdout, for testing away from the device."""
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            message = json.loads(raw)
        except ValueError as exc:
            reply = {"id": 0, "ok": False, "error": "bad request: %s" % exc}
        else:
            reply = call(message.get("method", ""), message.get("params") or {})
            reply["id"] = message.get("id", 0)
        sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
