import QtQuick 2.6
import io.thp.pyotherside 1.5

/*!
    The app's only route to yt-dlp.

    Python runs in-process here rather than as a child process: Sailjail
    launches every app under firejail's --private-bin, which leaves only the
    app's own binary in /usr/bin, so there is no python3 to spawn. pyotherside
    embeds the interpreter and runs it on its own thread, so calls made here
    never block the UI.

    Every call reports failure through its callback's `ok` field. Python
    exceptions would otherwise arrive on pyotherside's global error signal,
    detached from the call that caused them.

    Instantiated once by the ApplicationWindow and reached as
    `app.extractor`. A qmldir singleton would be tidier, but singletons
    from a relative directory import are unreliable on Qt 5.6.
*/
QtObject {
    id: root

    property bool ready: false
    property string error: ""

    property var _py: Python {
        Component.onCompleted: {
            // qml/components -> the app's python/ directory
            addImportPath(Qt.resolvedUrl('../../python').toString().replace('file://', ''))
            importModule('moira_service', function () {
                root.ready = true
            })
        }
        onError: root.error = traceback
    }

    function _call(method, params, callback) {
        _py.call('moira_service.call', [method, params], function (reply) {
            callback(reply ? reply
                           : { ok: false, error: qsTr("No reply from the extractor") })
        })
    }

    function popular(limit, callback) {
        _call('popular', { "limit": limit }, callback)
    }

    function search(query, limit, callback) {
        _call('search', { "query": query, "limit": limit }, callback)
    }

    function stream(url, mode, maxHeight, callback) {
        _call('stream', { "url": url, "mode": mode, "max_height": maxHeight || 0 },
              callback)
    }

    function video(url, callback) {
        _call('video', { "url": url }, callback)
    }

    function updateCheck(callback) {
        _call('update_check', {}, callback)
    }

    function updateInstall(callback) {
        _call('update_install', {}, callback)
    }

    function ping(callback) {
        _call('ping', {}, callback)
    }
}
