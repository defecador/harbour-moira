# Moira

A native Sailfish OS client for watching and listening without an account,
ads or tracking — NewPipe's idea, rebuilt for Qt Quick / Silica.

Not a port. NewPipe is ~2.5 MB of Java plus 758 KB of Kotlin, and
NewPipeExtractor needs a JVM and Mozilla Rhino, neither of which exists on
Sailfish aarch64. Moira reimplements the *behaviour* on a stack the phone
actually has.

## Architecture

```
QML / Silica UI  ──D-Bus-ish JSON──▶  Python extractor service (yt-dlp)
       │              over stdio               │
       ▼                                       ▼
QtMultimedia → GStreamer              (planned) hidden Gecko WebView
       │                                        PO token provider
       ▼
SQLite: subscriptions, history, playlists
```

Extraction sits behind one narrow request/reply interface
(`src/extractorservice.h`). yt-dlp is today's implementation, not a
commitment: replacing it with a native InnerTube client should not touch
anything above that class.

### Wire protocol

Newline-delimited JSON on the child process's stdin/stdout:

```
-> {"id":1,"method":"search","params":{"query":"cats","limit":20}}
<- {"id":1,"ok":true,"result":{"items":[...]}}
<- {"id":1,"ok":false,"error":"..."}
```

Methods: `ping`, `search`, `video`, `stream`, `channel`. Each runs on a
worker thread, so replies can arrive out of order — callers match on `id`.

## Status

Verified end to end on a Jolla Phone (2026, MediaTek, aarch64) running
Sailfish OS 5.2.0.17: search, HLS video with hardware decode via `droidvdec`,
audio-only playback, and quality selection. Built against the 5.1.0.11 SDK
target, which is the newest Jolla publishes - 5.2 ships as an OS release with
no corresponding build target, and kept Qt 5.6.3, so the older target is
correct.

## Building

```bash
tools/vendor-ytdlp.sh                                  # fetch the dependency
sfdk -c target=SailfishOS-5.1.0.11-aarch64 build       # produces RPMS/*.rpm
```

Verified against Sailfish OS 5.1.0.11 (Qt 5.6.3, Python 3.11.15).

## Known constraints

**Video plays via HLS, not progressive.** YouTube no longer serves muxed
progressive formats at all - a representative video returns 48 formats, of
which **zero** are muxed. QtMultimedia 5.6 cannot merge separate audio and
video streams, so the service hands back the *master* HLS manifest instead:
its variants declare both `avc1` and `mp4a` with EXT-X-MEDIA audio groups, and
GStreamer's `hlsdemux` does the muxing itself. H.264 also keeps decoding on
the hardware path.

`max_height` is honoured by rewriting the master: variants above the cap are
stripped and the file is served locally. That is the only lever available -
adaptivedemux picks a variant by bandwidth on its own, and QtMultimedia 5.6
offers no way to constrain it. Two details are load-bearing. Every
`EXT-X-MEDIA` rendition is preserved, since variants reference them by AUDIO
group and dropping one silences the stream; and the local file is *not* named
`.m3u8`, because Qt would parse that as one of its own playlist formats
instead of handing it to GStreamer.

The same filter prefers `avc1` over `vp09` wherever both are offered, keeping
playback on the hardware decoder. vp09 survives only at 1440p and 2160p, where
YouTube offers nothing else.

Audio mode deliberately stays on a plain progressive URL (format 140, m4a
~129 kbps): one stream needs no muxing, and avoiding HLS keeps background
playback cheap.

**Sailjail rules out subprocesses.** Every app is launched under firejail with
`--private-bin=harbour-moira`, leaving three entries in `/usr/bin` and no
interpreter to spawn. This is why extraction runs in-process under pyotherside
rather than as a child process - see `qml/components/Extractor.qml`. `/usr/lib64`
is *not* restricted, so the plugin and `libpython3.11` load normally.

**PO tokens remain a live risk, but are not currently blocking.** Since 2024
YouTube has withheld formats from clients that cannot present a
proof-of-origin token. As of the last verified run both the HLS master and
adaptive audio resolve and fetch (HTTP 200) without one. That can change
without warning, which is why `_NO_FORMAT_MESSAGE` names the likely cause. The
contingency is a hidden `qtmozembed` WebView running BotGuard on-device.

**Distribution is OpenRepos or Chum, not Harbour.** Bundled Python
dependencies and the nature of the app both rule out Jolla's store.

## Licence

GPLv3, matching NewPipe. The name and icon are deliberately not NewPipe's.
