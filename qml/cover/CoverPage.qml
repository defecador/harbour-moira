import QtQuick 2.6
import Sailfish.Silica 1.0

CoverBackground {
    Column {
        anchors.centerIn: parent
        width: parent.width - Theme.paddingLarge * 2
        spacing: Theme.paddingMedium

        Label {
            width: parent.width
            text: "Moira"
            font.pixelSize: Theme.fontSizeLarge
            horizontalAlignment: Text.AlignHCenter
        }

        Label {
            width: parent.width
            text: app.nowPlayingTitle
            visible: app.nowPlayingTitle !== ""
            wrapMode: Text.WordWrap
            maximumLineCount: 3
            truncationMode: TruncationMode.Elide
            font.pixelSize: Theme.fontSizeExtraSmall
            color: Theme.secondaryColor
            horizontalAlignment: Text.AlignHCenter
        }
    }
}
