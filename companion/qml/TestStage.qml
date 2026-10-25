import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Wayland

// Explicit verification-only backdrop. It never becomes a production surface.
PanelWindow {
    id: stage
    property bool lowered: false
    required property var output
    property bool fieldFocused: fixture.activeFocus
    property int fieldLength: fixture.text.length
    screen: output
    anchors {
        left: true
        right: true
        top: true
        bottom: true
    }
    color: "#101115"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.namespace: "capri-v2-verification-stage"
    WlrLayershell.layer: WlrLayer.Bottom
    WlrLayershell.keyboardFocus: lowered ? WlrKeyboardFocus.None : WlrKeyboardFocus.OnDemand
    mask: Region {
        item: stage.lowered ? null : fixture
    }
    TextField {
        id: fixture
        x: 24
        y: 24
        width: 360
        height: 44
        placeholderText: "Native pass-through fixture"
        onActiveFocusChanged: if (activeFocus)
            console.log("BACKGROUND_FOCUS")
        onTextChanged: console.log("BACKGROUND_TYPED")
    }
    Text {
        x: 24
        y: 900
        text: "Capri · native verification stage"
        color: "#a5a2af"
        font.pixelSize: 15
    }
}
