import QtQuick
import QtQuick.Controls
import "../qml"
ApplicationWindow {
    id: window
    width: 480; height: 560; visible: true
    QtObject {
        id: fixture
        property bool busy: false
        property var profile: ({ui_text_scale:100})
        property var snapshot: ({partition:'public-fixture',tasks:[],activity:[],scope:{roots:[]}})
        function send(kind,args) { throw Error('No real actions in presentation fixture'); }
    }
    ActivityView { id: activity; anchors.fill: parent; owner: fixture }
    Timer {
        interval: 80; running: true; repeat: false
        onTriggered: {
            // The hidden zero-width scope view formerly hung before this timer.
            fixture.snapshot={partition:'public-fixture',tasks:[],activity:[],scope:{roots:[]},scope_request:{id:'public-request',reason:'Read the additional public project directory.',roots:['/public/project'],desktop:false}};
            verify.restart();
        }
    }
    Timer {
        id: verify; interval: 100
        onTriggered: {
            if (activity.contentWidth > activity.width + 1 || activity.contentHeight < 100)
                throw Error('Native scope layout is clipped or empty');
            console.warn('PRESENTATION_PASS');Qt.exit(0);
        }
    }
}
