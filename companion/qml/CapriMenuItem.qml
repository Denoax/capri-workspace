import QtQuick
import QtQuick.Controls
import "Theme.js" as Theme

MenuItem {
    implicitHeight: Math.max(44, contentItem.implicitHeight + 20)
    font.family: "Inter"
    leftPadding: 14
    rightPadding: 14
    Accessible.name: text
}
