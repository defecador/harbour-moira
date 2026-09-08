import QtQuick 2.6
import Sailfish.Silica 1.0
import "../components"
import "../components/Format.js" as Format

Page {
    id: page
    allowedOrientations: Orientation.All

    property bool loading: false
    property string errorText: ""

    // "popular" until the user searches; searching switches the list over,
    // clearing the field switches it back.
    property string mode: "popular"
    property bool installing: false
    property string setupError: ""

    // A package built on OBS ships without yt-dlp, so the first launch has to
    // offer to fetch it rather than just failing to search.
    readonly property bool needsSetup: app.extractor.ready
                                       && !app.extractor.available
                                       && !installing

    function installExtractor() {
        installing = true
        setupError = ""
        app.extractor.updateInstall(function (reply) {
            if (!reply.ok) {
                page.installing = false
                page.setupError = reply.error
                return
            }
            app.extractor.refreshAvailability(function () {
                page.installing = false
                if (app.extractor.available) {
                    page.loadPopular()
                }
            })
        })
    }

    ListModel {
        id: results
    }

    function _fill(reply) {
        page.loading = false
        if (!reply.ok) {
            page.errorText = reply.error
            return
        }
        var items = reply.result.items
        for (var i = 0; i < items.length; i++) {
            results.append(items[i])
        }
    }

    function loadPopular() {
        page.mode = "popular"
        results.clear()
        errorText = ""
        loading = true
        app.extractor.popular(20, _fill)
    }

    function runSearch(text) {
        var query = text.trim()
        if (query === "") {
            loadPopular()
            return
        }
        page.mode = "search"
        results.clear()
        errorText = ""
        loading = true
        app.extractor.search(query, 20, _fill)
    }

    // The interpreter imports its module asynchronously, so the first load
    // waits for the extractor rather than firing on page creation.
    Component.onCompleted: if (app.extractor.available) loadPopular()

    Connections {
        target: app.extractor
        onAvailableChanged: {
            if (app.extractor.available && results.count === 0 && !page.loading) {
                page.loadPopular()
            }
        }
    }

    SilicaListView {
        id: listView
        anchors.fill: parent
        model: results
        visible: !page.needsSetup && !page.installing

        PullDownMenu {
            MenuItem {
                text: qsTr("About & updates")
                onClicked: pageStack.push(Qt.resolvedUrl("AboutPage.qml"))
            }
            MenuItem {
                text: qsTr("Popular this week")
                onClicked: page.loadPopular()
            }
        }

        header: Column {
            width: listView.width

            PageHeader {
                title: qsTr("Moira")
                description: page.mode === "popular" ? qsTr("Popular this week")
                                                     : qsTr("Search results")
            }

            SearchField {
                width: parent.width
                placeholderText: qsTr("Search videos")
                inputMethodHints: Qt.ImhNoAutoUppercase | Qt.ImhNoPredictiveText
                enabled: app.extractor.ready

                EnterKey.iconSource: "image://theme/icon-m-enter-accept"
                EnterKey.onClicked: {
                    focus = false
                    page.runSearch(text)
                }
            }
        }

        delegate: ListItem {
            id: delegate
            width: listView.width
            contentHeight: Math.max(thumbnail.height, textColumn.height) + Theme.paddingMedium

            onClicked: pageStack.push(Qt.resolvedUrl("VideoPage.qml"), {
                videoUrl: model.url,
                videoTitle: model.title,
                uploader: model.uploader,
                thumbnail: model.thumbnail
            })

            Row {
                anchors {
                    verticalCenter: parent.verticalCenter
                    left: parent.left
                    right: parent.right
                    leftMargin: Theme.horizontalPageMargin
                    rightMargin: Theme.horizontalPageMargin
                }
                spacing: Theme.paddingMedium

                StreamThumbnail {
                    id: thumbnail
                    anchors.verticalCenter: parent.verticalCenter
                    source: model.thumbnail
                    duration: model.duration
                }

                Column {
                    id: textColumn
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - thumbnail.width - Theme.paddingMedium

                    Label {
                        width: parent.width
                        text: model.title
                        maximumLineCount: 2
                        wrapMode: Text.WordWrap
                        truncationMode: TruncationMode.Elide
                        font.pixelSize: Theme.fontSizeSmall
                        color: delegate.highlighted ? Theme.highlightColor
                                                    : Theme.primaryColor
                    }

                    Label {
                        width: parent.width
                        text: {
                            var views = Format.count(model.viewCount)
                            return views ? model.uploader + " · " + qsTr("%1 views").arg(views)
                                         : model.uploader
                        }
                        truncationMode: TruncationMode.Elide
                        font.pixelSize: Theme.fontSizeExtraSmall
                        color: delegate.highlighted ? Theme.secondaryHighlightColor
                                                    : Theme.secondaryColor
                    }
                }
            }
        }

        ViewPlaceholder {
            enabled: results.count === 0 && !page.loading
                     && page.errorText === "" && app.extractor.ready
            text: qsTr("Nothing to show")
            hintText: qsTr("Pull down to refresh")
        }

        ViewPlaceholder {
            enabled: !app.extractor.ready && app.extractor.error === ""
            text: qsTr("Starting extractor")
        }

        ViewPlaceholder {
            enabled: page.errorText !== "" || app.extractor.error !== ""
            text: qsTr("Extraction failed")
            hintText: page.errorText !== "" ? page.errorText : app.extractor.error
        }

        VerticalScrollDecorator {}
    }

    BusyIndicator {
        anchors.centerIn: parent
        size: BusyIndicatorSize.Large
        running: page.loading || page.installing
    }

    Column {
        id: setupPrompt
        visible: page.needsSetup
        anchors.centerIn: parent
        width: parent.width - Theme.horizontalPageMargin * 2
        spacing: Theme.paddingLarge

        Label {
            width: parent.width
            text: qsTr("Extractor needed")
            font.pixelSize: Theme.fontSizeLarge
            horizontalAlignment: Text.AlignHCenter
        }

        Label {
            width: parent.width
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            font.pixelSize: Theme.fontSizeExtraSmall
            color: Theme.secondaryColor
            text: qsTr("Moira needs yt-dlp before it can search or play anything. "
                     + "About 3 MB, checked against the checksum published with it.")
        }

        Button {
            anchors.horizontalCenter: parent.horizontalCenter
            text: qsTr("Download extractor")
            onClicked: page.installExtractor()
        }

        Label {
            width: parent.width
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            visible: page.setupError !== ""
            text: page.setupError
            font.pixelSize: Theme.fontSizeExtraSmall
            color: Theme.errorColor
        }
    }
}
