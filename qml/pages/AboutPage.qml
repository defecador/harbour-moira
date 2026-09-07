import QtQuick 2.6
import Sailfish.Silica 1.0

Page {
    id: page
    allowedOrientations: Orientation.All

    property string ytdlpVersion: ""
    property string latestVersion: ""
    property string extractorSource: ""
    property bool updateAvailable: false
    property bool busy: false
    property string statusText: ""
    property bool restartNeeded: false

    function refresh() {
        busy = true
        statusText = ""
        app.extractor.updateCheck(function (reply) {
            page.busy = false
            if (!reply.ok) {
                page.statusText = reply.error
                return
            }
            page.ytdlpVersion = reply.result.current
            page.latestVersion = reply.result.latest
            page.extractorSource = reply.result.source
            page.updateAvailable = reply.result.updateAvailable
        })
    }

    function install() {
        busy = true
        statusText = qsTr("Downloading and verifying…")
        app.extractor.updateInstall(function (reply) {
            page.busy = false
            if (!reply.ok) {
                page.statusText = reply.error
                return
            }
            page.restartNeeded = reply.result.restartRequired
            page.updateAvailable = false
            page.ytdlpVersion = reply.result.installed
            page.statusText = qsTr("Installed %1").arg(reply.result.installed)
        })
    }

    Component.onCompleted: refresh()

    SilicaFlickable {
        anchors.fill: parent
        contentHeight: content.height

        Column {
            id: content
            width: parent.width
            spacing: Theme.paddingMedium
            bottomPadding: Theme.paddingLarge

            PageHeader {
                title: qsTr("About Moira")
            }

            Label {
                x: Theme.horizontalPageMargin
                width: parent.width - Theme.horizontalPageMargin * 2
                wrapMode: Text.WordWrap
                font.pixelSize: Theme.fontSizeExtraSmall
                color: Theme.secondaryColor
                text: qsTr("Watch and listen without an account, ads or tracking.")
            }

            DetailItem {
                label: qsTr("Version")
                value: appVersion
            }

            DetailItem {
                label: qsTr("Extractor")
                value: page.ytdlpVersion === "" ? qsTr("unknown")
                     : page.ytdlpVersion + " (" + page.extractorSource + ")"
            }

            DetailItem {
                label: qsTr("Latest available")
                value: page.latestVersion === "" ? "…" : page.latestVersion
                visible: page.latestVersion !== ""
            }

            Label {
                x: Theme.horizontalPageMargin
                width: parent.width - Theme.horizontalPageMargin * 2
                wrapMode: Text.WordWrap
                font.pixelSize: Theme.fontSizeExtraSmall
                color: Theme.secondaryColor
                text: qsTr("YouTube changes often enough to break extraction between releases. Updating replaces the bundled extractor with the latest published one, after checking it against its SHA-256 checksum.")
            }

            Button {
                anchors.horizontalCenter: parent.horizontalCenter
                enabled: !page.busy
                text: page.updateAvailable ? qsTr("Update extractor")
                                           : qsTr("Reinstall extractor")
                onClicked: page.install()
            }

            Button {
                anchors.horizontalCenter: parent.horizontalCenter
                enabled: !page.busy
                text: qsTr("Check again")
                onClicked: page.refresh()
            }

            Label {
                x: Theme.horizontalPageMargin
                width: parent.width - Theme.horizontalPageMargin * 2
                wrapMode: Text.WordWrap
                visible: page.statusText !== ""
                text: page.statusText
                font.pixelSize: Theme.fontSizeExtraSmall
                color: Theme.highlightColor
            }

            Label {
                x: Theme.horizontalPageMargin
                width: parent.width - Theme.horizontalPageMargin * 2
                wrapMode: Text.WordWrap
                visible: page.restartNeeded
                text: qsTr("Restart Moira to use the new extractor.")
                font.pixelSize: Theme.fontSizeExtraSmall
                color: Theme.errorColor
            }
        }

        BusyIndicator {
            anchors.centerIn: parent
            size: BusyIndicatorSize.Large
            running: page.busy
        }

        VerticalScrollDecorator {}
    }
}
