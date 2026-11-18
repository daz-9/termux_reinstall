    readonly property var calendarHeaders: ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    readonly property var monthNames: [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    readonly property var monthShort: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    property int calViewYear: (new Date()).getFullYear()
    property int calViewMonth: (new Date()).getMonth()
    property string calMonthTitle: monthNames[calViewMonth] + " " + calViewYear
    property string calSelectedDateKey: ""
    property var calGridCells: []
    property bool calendarOk: false
    property var agendaEvents: []
