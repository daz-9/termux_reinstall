    function dateKey(y, m, d) {
        return y + "-" + (m + 1) + "-" + d;
    }

    function eventDateParts(ev) {
        const dt = new Date(Number(ev.begin_ms) || 0);
        if (ev.all_day) {
            return { y: dt.getUTCFullYear(), m: dt.getUTCMonth(), d: dt.getUTCDate(), hh: 0, mm: 0 };
        }
        return { y: dt.getFullYear(), m: dt.getMonth(), d: dt.getDate(), hh: dt.getHours(), mm: dt.getMinutes() };
    }

    function eventDateKey(ev) {
        const p = eventDateParts(ev);
        return dateKey(p.y, p.m, p.d);
    }

    function rebuildCalendarGrid() {
        const y = root.calViewYear;
        const m = root.calViewMonth;
        root.calMonthTitle = root.monthNames[m] + " " + y;

        const eventMap = {};
        const evs = root.agendaEvents || [];
        for (let i = 0; i < evs.length; i++) {
            eventMap[eventDateKey(evs[i])] = true;
        }

        const now = new Date();
        const todayKey = dateKey(now.getFullYear(), now.getMonth(), now.getDate());
        const first = new Date(y, m, 1);
        const startOffset = (first.getDay() + 6) % 7; // Monday = 0
        const daysInMonth = new Date(y, m + 1, 0).getDate();
        const prevDays = new Date(y, m, 0).getDate();
        const totalCells = (startOffset + daysInMonth) > 35 ? 42 : 35;

        const cells = [];
        for (let idx = 0; idx < totalCells; idx++) {
            const col = idx % 7;
            const isWknd = (col === 5 || col === 6);
            if (idx < startOffset) {
                const d = prevDays - startOffset + 1 + idx;
                const pm = m === 0 ? 11 : m - 1;
                const py = m === 0 ? y - 1 : y;
                const k = dateKey(py, pm, d);
                cells.push({ d: String(d), key: k, cls: "muted", hasEvent: Boolean(eventMap[k]) });
            } else if (idx < startOffset + daysInMonth) {
                const d = idx - startOffset + 1;
                const k = dateKey(y, m, d);
                const cls = (k === todayKey) ? "today" : (isWknd ? "wknd" : "");
                cells.push({ d: String(d), key: k, cls: cls, hasEvent: Boolean(eventMap[k]) });
            } else {
                const d = idx - (startOffset + daysInMonth) + 1;
                const nm = m === 11 ? 0 : m + 1;
                const ny = m === 11 ? y + 1 : y;
                const k = dateKey(ny, nm, d);
                cells.push({ d: String(d), key: k, cls: "muted", hasEvent: Boolean(eventMap[k]) });
            }
        }
        root.calGridCells = cells;
    }

    function queryCalendarMonth(y, m) {
        if (!mediaStreamProc.running) {
            mediaStreamProc.running = true;
        }
        const startMs = new Date(y, m, -6).getTime();
        const endMs = new Date(y, m + 2, 15).getTime();
        mediaStreamProc.write("calendar\t" + startMs + "\t" + endMs + "\n");
    }

    function stepCalendarMonth(delta) {
        let m = root.calViewMonth + delta;
        let y = root.calViewYear;
        while (m < 0) { m += 12; y -= 1; }
        while (m > 11) { m -= 12; y += 1; }
        root.calViewYear = y;
        root.calViewMonth = m;
        root.rebuildCalendarGrid();
        root.queryCalendarMonth(y, m);
    }

    function resetCalendarToday() {
        const now = new Date();
        root.calViewYear = now.getFullYear();
        root.calViewMonth = now.getMonth();
        root.calSelectedDateKey = "";
        root.rebuildCalendarGrid();
        root.queryCalendarMonth(root.calViewYear, root.calViewMonth);
    }

    function toggleCalendarDay(cell) {
        if (!cell || cell.cls === "muted") return;
        root.calSelectedDateKey = (root.calSelectedDateKey === cell.key) ? "" : cell.key;
    }

    function filteredAgendaEvents() {
        const evs = root.agendaEvents || [];
        const sel = root.calSelectedDateKey;
        const out = [];
        const now = new Date();
        const todayStartMs = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();

        for (let i = 0; i < evs.length; i++) {
            const ev = evs[i];
            if (sel.length > 0) {
                if (eventDateKey(ev) === sel) out.push(ev);
            } else {
                const cmpMs = (ev.end_ms && ev.end_ms > 0) ? ev.end_ms : ev.begin_ms;
                if (cmpMs >= todayStartMs) out.push(ev);
            }
        }
        return out.slice(0, 5);
    }

    function formatEventWhen(ev) {
        const p = eventDateParts(ev);
        const now = new Date();
        const isToday = (p.y === now.getFullYear() && p.m === now.getMonth() && p.d === now.getDate());
        const dStr = p.d + " " + root.monthShort[p.m];
        if (ev.all_day) {
            return isToday ? "Today" : dStr;
        }
        const hh = p.hh < 10 ? "0" + p.hh : String(p.hh);
        const mm = p.mm < 10 ? "0" + p.mm : String(p.mm);
        return (isToday || root.calSelectedDateKey.length > 0) ? (hh + ":" + mm) : (dStr + " " + hh + ":" + mm);
    }

    function eventColor(ev) {
        const cid = Number(ev.cal_id) || 0;
        if (cid % 4 === 1) return root.colBlue;
        if (cid % 4 === 2) return root.colMauve;
        if (cid % 4 === 3) return root.colTeal;
        return root.colPeach;
    }
