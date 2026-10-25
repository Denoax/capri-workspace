import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import "Theme.js" as Theme

FloatingWindow {
    id: review
    required property var owner
    required property var actor
    property bool coverage: false
    property var sequence: []
    property int sequenceIndex: 0
    title: 'Capri · Motion review'
    implicitWidth: 400
    implicitHeight: 650
    minimumSize: Qt.size(340, 440)
    visible: owner.motionReviewOpen && !owner.snapshot.locked
    color: 'transparent'
    function choose() {
        var c = actor.catalog[clips.currentIndex];
        if (c?.asset_status === 'AVAILABLE') {
            coverage = false;
            actor.review(c.id, 0, true);
        }
    }
    function next() {
        if (!sequence.length)
            return;
        sequenceIndex++;
        if (sequenceIndex >= sequence.length) {
            coverage = false;
            return;
        }
        clips.currentIndex = sequence[sequenceIndex];
        actor.reviewing = true;
        actor.reviewPaused = false;
        actor.play(actor.catalog[sequence[sequenceIndex]].id);
    }
    function startCoverage() {
        actor.reviewAngle = 0;
        actor.reviewEmotion = "";
        var seed = 71;
        sequence = actor.catalog.map((c, i) => c.asset_status === 'AVAILABLE' ? i : -1).filter(i => i >= 0);
        for (var i = sequence.length - 1; i > 0; i--) {
            seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
            var j = seed % (i + 1), v = sequence[i];
            sequence[i] = sequence[j];
            sequence[j] = v;
        }
        coverage = true;
        sequenceIndex = -1;
        next();
    }
    function closeReview() {
        coverage = false;
        actor.endReview();
        owner.motionReviewOpen = false;
    }
    Connections {
        target: review.actor
        function onClipFinished(name) {
            if (review.coverage)
                Qt.callLater(() => review.next());
        }
    }
    onVisibleChanged: if (!visible && owner.motionReviewOpen && !owner.snapshot.locked)
        Qt.callLater(() => review.closeReview())
    Pane {
        anchors.fill: parent
        padding: 20
        font.family: 'Inter'
        font.pixelSize: 15 * (owner.profile.ui_text_scale || 100) / 100
        background: Rectangle {
            color: Theme.surface
            radius: 26
            border.color: Theme.outline
        }
        ScrollView {
            id: reviewScroll
            anchors.fill: parent
            clip: true
            contentWidth: availableWidth
            contentHeight: reviewColumn.implicitHeight
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ColumnLayout {
                id: reviewColumn
                width: reviewScroll.availableWidth
                spacing: 16
                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        text: 'Motion review'
                        font.pixelSize: 22
                        color: Theme.ink
                        Layout.fillWidth: true
                    }
                    CloseButton {
                        onClicked: review.closeReview()
                    }
                }
                CapriComboBox {
                    id: clips
                    Layout.fillWidth: true
                    model: review.actor.catalog
                    textRole: 'id'
                    onActivated: review.choose()
                }
                Text {
                    text: review.actor.catalog[clips.currentIndex]?.silhouette || ''
                    color: Theme.muted
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                Text {
                    visible: review.actor.catalog[clips.currentIndex]?.asset_status !== 'AVAILABLE'
                    text: 'Matching view unavailable. This brief is not counted as an implemented animation.'
                    color: Theme.pink
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                Text {
                    text: review.actor.clipId + ' · ' + Math.round(review.actor.clock) + 'ms'
                    textFormat: Text.PlainText
                    color: Theme.ink
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                Slider {
                    Layout.fillWidth: true
                    from: 0
                    to: review.actor.currentClip?.duration_ms || 1
                    value: review.actor.clock
                    onMoved: {
                        review.coverage = false;
                        review.actor.review(review.actor.clipId, Math.round(value), true);
                    }
                    Accessible.name: 'Scrub authored clip phases'
                }
                Flow {
                    Layout.fillWidth: true
                    spacing: 8
                    CapriButton {
                        text: review.actor.reviewPaused ? 'Play' : 'Pause'
                        onClicked: {
                            review.coverage = false;
                            if (!review.actor.currentClip)
                                review.choose();
                            review.actor.reviewPaused = !review.actor.reviewPaused;
                            review.actor.moving = true;
                        }
                    }
                    CapriButton {
                        text: 'From start'
                        onClicked: {
                            review.coverage = false;
                            review.actor.reviewing = true;
                            review.actor.reviewPaused = false;
                            review.actor.play(review.actor.clipId);
                        }
                    }
                    CapriButton {
                        text: 'Next clip'
                        onClicked: {
                            coverage = false;
                            clips.currentIndex = (clips.currentIndex + 1) % actor.catalog.length;
                            review.choose();
                        }
                    }
                    CapriButton {
                        text: 'Seeded coverage'
                        onClicked: review.startCoverage()
                    }
                }
                Text {
                    text: review.coverage ? 'Coverage ' + (review.sequenceIndex + 1) + ' / ' + review.sequence.length : 'Review changes presentation only. Native work and Stop remain independent.'
                    color: Theme.muted
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                CapriComboBox {
                    Layout.fillWidth: true
                    model: ['Clip expression', 'happy', 'curious', 'puzzled', 'amused', 'annoyed', 'startled', 'focused', 'sleepy']
                    onActivated: review.actor.reviewEmotion = currentIndex ? currentText : ''
                    Accessible.name: 'Authored facial expression'
                }
                Text {
                    text: 'Review angle'
                    color: Theme.muted
                }
                Slider {
                    Layout.fillWidth: true
                    from: -180
                    to: 180
                    stepSize: 5
                    value: review.actor.reviewAngle
                    onMoved: review.actor.reviewAngle = value
                    Accessible.name: 'Review angle, degrees'
                }
                Text {
                    text: 'Owner size'
                    color: Theme.muted
                }
                Slider {
                    Layout.fillWidth: true
                    from: 160
                    to: 420
                    stepSize: 10
                    value: owner.profile.character_size || 280
                    onMoved: owner.preference('character_size', Math.round(value))
                    Accessible.name: 'Character review size'
                }
                Text {
                    text: 'Source catalogue:48 briefs. ' + review.actor.catalog.filter(c => c.asset_status === 'AVAILABLE').length + ' authored sequences; native and owner review are separate.'
                    color: Theme.muted
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                    font.pixelSize: 13
                }
            }
        }
    }
}
