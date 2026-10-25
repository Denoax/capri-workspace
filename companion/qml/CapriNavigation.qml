import QtQuick
import QtQuick.Layouts
import "Theme.js" as Theme

Rectangle {
    id: nav
    property int currentIndex: 0
    property real textScale: 1
    property bool reduced: false
    function reviewState() {
        return row.children.filter(i => i.objectName === "nav-segment").map(i => ({
                    index: i.index,
                    label: i.modelData,
                    color: i.labelColor,
                    visible: i.labelVisible,
                    opacity: i.labelOpacity,
                    width: i.width,
                    height: i.height
                }));
    }
    signal selected(int index)
    // Cache segment paint and labels together during software-rendered pane swaps.
    layer.enabled: true
    color: Theme.raised
    radius: 16
    implicitHeight: Math.max(52, 30 * textScale + 22)
    RowLayout {
        id: row
        anchors.fill: parent
        anchors.margins: 4
        spacing: 0
        Repeater {
            model: ['Talk', 'Activity', 'Settings']
            delegate: Item {
                id: segment
                objectName: "nav-segment"
                readonly property color labelColor: caption.color
                readonly property bool labelVisible: caption.visible
                readonly property real labelOpacity: caption.opacity
                required property int index
                required property string modelData
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                Layout.fillHeight: true
                CapriButton {
                    id: button
                    anchors.fill: parent
                    text: ''
                    flat: true
                    Accessible.name: segment.modelData
                    Accessible.role: Accessible.PageTab
                    Accessible.selected: nav.currentIndex === segment.index
                    contentItem: Item {}
                    background: Rectangle {
                        radius: 12
                        color: nav.currentIndex === segment.index ? Theme.green : button.hovered ? Theme.surface : 'transparent'
                        border.width: 2
                        border.color: button.visualFocus ? Theme.pink : 'transparent'
                        Behavior on color {
                            ColorAnimation {
                                duration: nav.reduced ? 0 : 180
                            }
                        }
                    }
                    onClicked: nav.selected(segment.index)
                }
                Text {
                    id: caption
                    anchors.fill: parent
                    z: 1
                    text: segment.modelData
                    font.family: 'Inter'
                    font.pixelSize: 14 * nav.textScale
                    font.weight: Font.Medium
                    color: nav.currentIndex === segment.index ? Theme.onGreen : Theme.muted
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    Accessible.ignored: true
                }
            }
        }
    }
}
