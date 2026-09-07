import QtQuick 2.6
import Sailfish.Silica 1.0
import "Format.js" as Format

/*! Thumbnail with a duration badge, sized to the standard 16:9 ratio. */
Item {
    id: root

    property alias source: image.source
    property int duration: 0

    width: Theme.itemSizeExtraLarge * 1.4
    height: width * 9 / 16

    Rectangle {
        anchors.fill: parent
        color: Theme.rgba(Theme.highlightBackgroundColor, 0.1)
        visible: image.status !== Image.Ready
    }

    Image {
        id: image
        anchors.fill: parent
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        clip: true
        sourceSize.width: width
    }

    BusyIndicator {
        anchors.centerIn: parent
        size: BusyIndicatorSize.Small
        running: image.status === Image.Loading
    }

    Rectangle {
        anchors {
            right: parent.right
            bottom: parent.bottom
            margins: Theme.paddingSmall
        }
        width: durationLabel.width + Theme.paddingSmall * 2
        height: durationLabel.height + Theme.paddingSmall
        radius: Theme.paddingSmall / 2
        color: Theme.rgba("black", 0.7)
        visible: durationLabel.text !== ""

        Label {
            id: durationLabel
            anchors.centerIn: parent
            text: Format.duration(root.duration)
            font.pixelSize: Theme.fontSizeExtraSmall
            color: "white"
        }
    }
}
