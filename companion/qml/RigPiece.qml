import QtQuick

Item {
    id: piece
    required property var part
    required property var rectangle
    required property var matrix
    required property string imageSource
    required property real textureFactor
    readonly property bool ready: image.status === Image.Ready
    transform: Matrix4x4 {
        matrix: Qt.matrix4x4(piece.matrix[0], -piece.matrix[1], 0, piece.matrix[2], piece.matrix[1], piece.matrix[0], 0, piece.matrix[3], 0, 0, 1, 0, 0, 0, 0, 1)
    }
    Item {
        x: piece.rectangle[0]
        y: piece.rectangle[1]
        width: piece.rectangle[2]
        height: piece.rectangle[3]
        clip: true
        Image {
            id: image
            x: piece.part.origin[0] - piece.rectangle[0]
            y: piece.part.origin[1] - piece.rectangle[1]
            width: piece.part.size[0]
            height: piece.part.size[1]
            source: piece.imageSource
            // Owner size/DPI select a stable decode bucket. Temporary pose scale
            // never reallocates the decoded image on animation frames.
            sourceSize: Qt.size(Math.ceil(width * piece.textureFactor / 64) * 64, Math.ceil(height * piece.textureFactor / 64) * 64)
            asynchronous: true
            smooth: true
            cache: true
        }
    }
}
