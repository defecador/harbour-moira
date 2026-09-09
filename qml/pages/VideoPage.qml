import QtQuick 2.6
import QtMultimedia 5.6
import Sailfish.Silica 1.0
import "../components"
import "../components/Format.js" as Format

Page {
    id: page
    allowedOrientations: Orientation.All

    property string videoUrl
    property string videoTitle
    property string uploader
    property string thumbnail

    property bool audioOnly: false
    property string errorText: ""
    property bool resolving: false

    // 0 means let the demuxer choose freely; otherwise an upper bound in
    // pixels of height. Populated from the stream reply.
    property int maxHeight: 0
    property var qualities: []

    // Position to restore after re-resolving, so changing quality does not
    // send the viewer back to the start.
    property int resumePosition: 0

    // Guards against a superseded resolve landing after a newer one and
    // swapping the stream under the user.
    property int _generation: 0

    function resolveStream() {
        var generation = ++page._generation
        errorText = ""
        resolving = true
        player.stop()

        app.extractor.stream(videoUrl, audioOnly ? "audio" : "video",
                             page.maxHeight, function (reply) {
            if (generation !== page._generation) {
                return
            }
            page.resolving = false
            if (!reply.ok) {
                page.errorText = reply.error
                return
            }
            if (reply.result.qualities) {
                page.qualities = reply.result.qualities
            }
            player.source = reply.result.url
            player.play()
        })
    }

    function setQuality(height) {
        if (height === page.maxHeight) {
            return
        }
        page.maxHeight = height
        page.resumePosition = player.position
        resolveStream()
    }

    Component.onCompleted: resolveStream()
    onAudioOnlyChanged: resolveStream()
    Component.onDestruction: player.stop()

    // Video playing, not paused, not audio-only: the only case where the
    // display must stay awake. Audio-only deliberately lets it blank.
    readonly property bool videoPlaying: !audioOnly
        && player.playbackState === MediaPlayer.PlayingState

    Loader {
        active: page.videoPlaying
        source: Qt.resolvedUrl("../components/KeepDisplayOn.qml")
        onStatusChanged: {
            if (status === Loader.Error) {
                console.warn("moira: Nemo.KeepAlive unavailable, display may blank")
            }
        }
    }

    MediaPlayer {
        id: player
        autoLoad: true

        onPlaybackStateChanged: {
            app.playing = (playbackState === MediaPlayer.PlayingState)
            if (playbackState === MediaPlayer.PlayingState) {
                app.nowPlayingTitle = page.videoTitle
            }
        }
        onErrorStringChanged: {
            if (errorString !== "") {
                page.errorText = errorString
            }
        }
        onSeekableChanged: {
            // A freshly loaded stream is not seekable immediately, so the
            // resume has to wait for the demuxer rather than follow play().
            if (seekable && page.resumePosition > 0) {
                seek(page.resumePosition)
                page.resumePosition = 0
            }
        }
    }

    SilicaFlickable {
        anchors.fill: parent
        contentHeight: content.height

        PullDownMenu {
            MenuItem {
                text: page.audioOnly ? qsTr("Play video") : qsTr("Audio only")
                onClicked: page.audioOnly = !page.audioOnly
            }
            MenuItem {
                text: qsTr("Reload")
                onClicked: page.resolveStream()
            }
        }

        Column {
            id: content
            width: parent.width
            spacing: Theme.paddingMedium

            Item {
                width: parent.width
                // 16:9 from the width overflows the screen in landscape, so
                // clamp it and leave room for the scrubber below.
                height: Math.min(width * 9 / 16, page.height * 0.82)

                Image {
                    anchors.fill: parent
                    source: page.thumbnail
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    clip: true
                    visible: page.audioOnly || !videoOutput.visible
                }

                VideoOutput {
                    id: videoOutput
                    anchors.fill: parent
                    source: player
                    fillMode: VideoOutput.PreserveAspectFit
                    visible: !page.audioOnly
                             && player.playbackState !== MediaPlayer.StoppedState
                }

                BusyIndicator {
                    anchors.centerIn: parent
                    size: BusyIndicatorSize.Large
                    running: page.resolving
                }

                MouseArea {
                    anchors.fill: parent
                    enabled: !page.resolving
                    onClicked: {
                        if (player.playbackState === MediaPlayer.PlayingState) {
                            player.pause()
                        } else {
                            player.play()
                        }
                    }
                }
            }

            Slider {
                width: parent.width
                minimumValue: 0
                maximumValue: Math.max(1, player.duration)
                value: player.position
                enabled: player.seekable
                valueText: Format.duration(value / 1000)
                    + " / " + Format.duration(player.duration / 1000)
                onReleased: player.seek(value)
            }

            ComboBox {
                width: parent.width
                label: qsTr("Quality")
                visible: !page.audioOnly && page.qualities.length > 0
                currentIndex: 0

                menu: ContextMenu {
                    MenuItem {
                        text: qsTr("Auto")
                        onClicked: page.setQuality(0)
                    }
                    Repeater {
                        model: page.qualities
                        MenuItem {
                            text: modelData + "p"
                            onClicked: page.setQuality(modelData)
                        }
                    }
                }
            }

            Column {
                width: parent.width - Theme.horizontalPageMargin * 2
                x: Theme.horizontalPageMargin

                Label {
                    width: parent.width
                    text: page.videoTitle
                    wrapMode: Text.WordWrap
                    font.pixelSize: Theme.fontSizeSmall
                }

                Label {
                    width: parent.width
                    text: page.uploader
                    truncationMode: TruncationMode.Elide
                    font.pixelSize: Theme.fontSizeExtraSmall
                    color: Theme.secondaryColor
                }
            }

            Label {
                x: Theme.horizontalPageMargin
                width: parent.width - Theme.horizontalPageMargin * 2
                text: page.errorText
                visible: page.errorText !== ""
                wrapMode: Text.WordWrap
                font.pixelSize: Theme.fontSizeExtraSmall
                color: Theme.errorColor
            }
        }
    }
}
