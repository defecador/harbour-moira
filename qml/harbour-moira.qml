import QtQuick 2.6
import Sailfish.Silica 1.0
import "pages"
import "cover"
import "components"

ApplicationWindow {
    id: app

    // Playback state lives at window scope so the cover and any page can
    // reach it, and so audio survives navigating away from the video page.
    property string nowPlayingTitle: ""
    property bool playing: false

    // One Python interpreter for the whole app; pages call app.extractor.
    property alias extractor: extractorImpl

    Extractor {
        id: extractorImpl
    }

    initialPage: Component { SearchPage {} }
    cover: Component { CoverPage {} }
    allowedOrientations: defaultAllowedOrientations
}
