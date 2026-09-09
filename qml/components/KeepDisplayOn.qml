import QtQuick 2.6
import Nemo.KeepAlive 1.2

/*!
    Holds off the display's auto-blank timeout.

    Loaded only while video is actually playing, so it is inert when paused
    and in audio-only mode - where blanking the screen is the entire point.

    Kept in its own file and reached through a Loader so that a device without
    the Nemo.KeepAlive plugin degrades to the old behaviour rather than
    failing to load the page. The plugin ships in libkeepalive, which the
    package requires, so that is a belt-and-braces measure.

    Talking to MCE is permitted inside the sandbox: Base.permission grants
    `dbus-system.talk com.nokia.mce`, and Base applies to every app.
*/
DisplayBlanking {
    preventBlanking: true
}
