/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart, onMounted, onWillUnmount, useRef } from "@odoo/owl";

const MONTHS = {
    '1':'يناير/Jan','2':'فبراير/Feb','3':'مارس/Mar','4':'أبريل/Apr',
    '5':'مايو/May','6':'يونيو/Jun','7':'يوليو/Jul','8':'أغسطس/Aug',
    '9':'سبتمبر/Sep','10':'أكتوبر/Oct','11':'نوفمبر/Nov','12':'ديسمبر/Dec',
};

function formatMoney(val) {
    if (val === undefined || val === null) return '0.00';
    return Number(val).toLocaleString('en-US', {
        minimumFractionDigits: 2, maximumFractionDigits: 2
    });
}

export class NahjDashboard extends Component {
    static template = "nahj_Tower.Dashboard";

    setup() {
        this.rpc = useService("rpc");
        this.action = useService("action");
        this.notification = useService("notification");
        this.canvasRef = useRef("cashFlowCanvas");
        this.donutRef  = useRef("donutCanvas");
        this._resizeObserver = null;

        this.state = useState({
            loading: true,
            selectedTower: null,
            selectedYear: new Date().getFullYear(),
            selectedPeriod: 'month',
            dateFrom: '',
            dateTo: '',
            data: {},
        });

        onWillStart(async () => { await this.loadData(); });
        onMounted(() => {
            this._drawCharts();
            this._setupResizeObserver();
        });
        onWillUnmount(() => {
            if (this._resizeObserver) this._resizeObserver.disconnect();
        });
    }

    _setupResizeObserver() {
        if (typeof ResizeObserver === 'undefined') return;
        this._resizeObserver = new ResizeObserver(() => {
            this._drawCharts();
        });
        if (this.canvasRef.el?.parentElement)
            this._resizeObserver.observe(this.canvasRef.el.parentElement);
        if (this.donutRef.el?.parentElement)
            this._resizeObserver.observe(this.donutRef.el.parentElement);
    }

    async loadData() {
        this.state.loading = true;
        try {
            const today   = new Date();
            const period  = this.state.selectedPeriod;
            const yr      = this.state.selectedYear || today.getFullYear();

            const params = {
                tower_id: this.state.selectedTower || null,
                year:     yr,
            };

            // Map period preset → params
            if (period === 'today') {
                const t = today.toISOString().split('T')[0];
                params.date_from = t;
                params.date_to   = t;
                params.year      = null;
            } else if (period === 'week') {
                const from = new Date(today); from.setDate(from.getDate() - 6);
                params.date_from = from.toISOString().split('T')[0];
                params.date_to   = today.toISOString().split('T')[0];
                params.year      = null;
            } else if (period === 'month') {
                params.year  = today.getFullYear();
                params.month = today.getMonth() + 1;
            } else if (period === 'quarter') {
                const qm     = Math.floor(today.getMonth() / 3) * 3;
                const qStart = new Date(today.getFullYear(), qm, 1);
                const qEnd   = new Date(today.getFullYear(), qm + 3, 0);
                params.date_from = qStart.toISOString().split('T')[0];
                params.date_to   = qEnd.toISOString().split('T')[0];
                params.year      = null;
            } else if (period === 'year') {
                params.year = today.getFullYear();
            } else if (/^([1-9]|1[0-2])$/.test(period)) {
                // Single calendar month within selected year
                params.month = parseInt(period);
            } else if (period === 'q1') {
                params.date_from = `${yr}-01-01`;
                params.date_to   = `${yr}-03-31`;
                params.year      = null;
            } else if (period === 'q2') {
                params.date_from = `${yr}-04-01`;
                params.date_to   = `${yr}-06-30`;
                params.year      = null;
            } else if (period === 'q3') {
                params.date_from = `${yr}-07-01`;
                params.date_to   = `${yr}-09-30`;
                params.year      = null;
            } else if (period === 'q4') {
                params.date_from = `${yr}-10-01`;
                params.date_to   = `${yr}-12-31`;
                params.year      = null;
            } else if (period === 'this_month') {
                params.year  = today.getFullYear();
                params.month = today.getMonth() + 1;
            } else if (period === 'last_month') {
                const d = new Date(today.getFullYear(), today.getMonth() - 1, 1);
                params.year  = d.getFullYear();
                params.month = d.getMonth() + 1;
            } else if (period === 'last_30') {
                const from = new Date(today); from.setDate(from.getDate() - 30);
                params.date_from = from.toISOString().split('T')[0];
                params.date_to   = today.toISOString().split('T')[0];
                params.year      = null;
            } else if (period === 'last_90') {
                const from = new Date(today); from.setDate(from.getDate() - 90);
                params.date_from = from.toISOString().split('T')[0];
                params.date_to   = today.toISOString().split('T')[0];
                params.year      = null;
            } else if (period === 'custom' && this.state.dateFrom && this.state.dateTo) {
                params.date_from = this.state.dateFrom;
                params.date_to   = this.state.dateTo;
                params.year      = null;
            }
            // 'all' → just year (existing behaviour)

            const data = await this.rpc("/nahj_tower/dashboard_data", params);
            this.state.data = data;
        } catch (e) {
            const detail = e?.data?.message || e?.message || String(e);
            this.notification && this.notification.add(
                'Failed to load dashboard data: ' + detail, { type: 'danger' });
            console.error('[NahjDashboard] loadData error:', e);
        } finally {
            this.state.loading = false;
        }
        setTimeout(() => this._drawCharts(), 50);
    }

    async onTowerChange(ev) {
        const val = ev.target.value;
        this.state.selectedTower = val ? parseInt(val) : null;
        await this.loadData();
    }

    async onYearChange(ev) {
        const val = ev.target.value;
        this.state.selectedYear = val ? parseInt(val) : new Date().getFullYear();
        await this.loadData();
    }

    async onPeriodBtnClick(ev) {
        this.state.selectedPeriod = ev.currentTarget.dataset.period;
        if (this.state.selectedPeriod !== 'custom') {
            await this.loadData();
        }
    }

    async onPeriodChange(ev) {
        this.state.selectedPeriod = ev.target.value;
        // For custom range, wait until both dates are filled
        if (this.state.selectedPeriod !== 'custom') {
            await this.loadData();
        }
    }

    async onDateFromChange(ev) {
        this.state.dateFrom = ev.target.value;
        if (this.state.dateTo) await this.loadData();
    }

    async onDateToChange(ev) {
        this.state.dateTo = ev.target.value;
        if (this.state.dateFrom) await this.loadData();
    }

    // ── Chart Rendering ────────────────────────────────────────────────────
    _drawCharts() {
        this._drawCashFlow();
        this._drawDonut();
    }

    _drawCashFlow() {
        const canvas = this.canvasRef.el;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const flow = this.state.data.daily_flow || [];
        const W = canvas.offsetWidth || 500;
        const H = canvas.offsetHeight || 180;
        canvas.width = W;
        canvas.height = H;
        ctx.clearRect(0, 0, W, H);

        if (!flow.length) return;

        const allVals = flow.flatMap(d => [d.income, d.expense]);
        const maxVal  = Math.max(...allVals, 1);
        const cols    = flow.length;
        const padL = 10, padR = 10, padT = 16, padB = 28;
        const bw  = (W - padL - padR) / cols;
        const bw2 = bw * 0.32;

        flow.forEach((d, i) => {
            const x = padL + i * bw + bw * 0.1;
            // Income bar
            const ih = ((d.income / maxVal) * (H - padT - padB)) || 2;
            ctx.fillStyle = '#1abc9c';
            ctx.beginPath();
            ctx.roundRect(x, H - padB - ih, bw2, ih, [4, 4, 0, 0]);
            ctx.fill();
            // Expense bar
            const eh = ((d.expense / maxVal) * (H - padT - padB)) || 2;
            ctx.fillStyle = '#e74c3c';
            ctx.beginPath();
            ctx.roundRect(x + bw2 + 2, H - padB - eh, bw2, eh, [4, 4, 0, 0]);
            ctx.fill();
            // Label
            ctx.fillStyle = '#888';
            ctx.font = '10px Cairo, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(d.label, x + bw2, H - 8);
        });

        // Legend
        ctx.fillStyle = '#1abc9c';
        ctx.fillRect(padL, 4, 12, 10);
        ctx.fillStyle = '#555';
        ctx.font = '10px Cairo, sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText('Income / دخل', padL + 16, 13);
        ctx.fillStyle = '#e74c3c';
        ctx.fillRect(padL + 90, 4, 12, 10);
        ctx.fillStyle = '#555';
        ctx.fillText('Expense / مصروف', padL + 106, 13);
    }

    _drawDonut() {
        const canvas = this.donutRef.el;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const cats = this.state.data.expense_chart || [];
        const W = canvas.offsetWidth || 180;
        const H = canvas.offsetHeight || 180;
        canvas.width = W;
        canvas.height = H;
        ctx.clearRect(0, 0, W, H);
        if (!cats.length) return;

        const total = cats.reduce((s, c) => s + c.value, 0) || 1;
        const COLORS = ['#3498db','#e74c3c','#2ecc71','#f39c12',
                        '#9b59b6','#1abc9c','#e67e22','#34495e'];
        const cx = W / 2, cy = H / 2;
        const outer = Math.min(W, H) / 2 - 4;
        const inner = outer * 0.55;
        let angle = -Math.PI / 2;

        cats.forEach((cat, i) => {
            const slice = (cat.value / total) * Math.PI * 2;
            ctx.beginPath();
            ctx.moveTo(cx, cy);
            ctx.arc(cx, cy, outer, angle, angle + slice);
            ctx.closePath();
            ctx.fillStyle = COLORS[i % COLORS.length];
            ctx.fill();
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 2;
            ctx.stroke();
            angle += slice;
        });

        // Inner hole
        ctx.beginPath();
        ctx.arc(cx, cy, inner, 0, Math.PI * 2);
        ctx.fillStyle = '#fff';
        ctx.fill();

        // Center text
        ctx.fillStyle = '#2c3e50';
        ctx.font = `bold 11px Cairo, sans-serif`;
        ctx.textAlign = 'center';
        ctx.fillText('مصاريف', cx, cy - 5);
        ctx.fillText('Expenses', cx, cy + 10);
    }

    // ── Navigation ─────────────────────────────────────────────────────────
    _doAction(xmlIdOrObj) {
        try {
            this.action.doAction(xmlIdOrObj);
        } catch (e) {
            this.notification && this.notification.add(
                'Navigation error: ' + e.message, { type: 'warning' });
        }
    }

    /**
     * Build an Odoo domain array that mirrors the active dashboard filters.
     * @param {'subscription'|'expense'|'unit'|'tower'} model
     * @param {Array}  extraDomain  additional conditions to AND in
     */
    _buildFilterDomain(model, extraDomain = []) {
        const domain = [...extraDomain];
        const p      = this.state.selectedPeriod;
        const yr     = this.state.selectedYear || new Date().getFullYear();
        const today  = new Date();

        // ── Tower filter ──────────────────────────────────────────────────
        if (this.state.selectedTower) {
            if (model === 'tower') {
                domain.push(['id', '=', this.state.selectedTower]);
            } else {
                domain.push(['tower_id', '=', this.state.selectedTower]);
            }
        }

        if (model === 'tower' || model === 'unit') {
            // Tower/unit records are not date-scoped; tower filter already applied
            return domain;
        }

        // ── Date / period filter ──────────────────────────────────────────
        const fmt = d => d.toISOString().split('T')[0];

        const applyDateRange = (from, to) => {
            if (model === 'subscription') {
                // Paid subs: filter by payment_date; unpaid: no date filter
                // Flat prefix Odoo domain: (state=paid AND payment_date>=from AND payment_date<=to) OR state=unpaid
                domain.push(
                    '|',
                    '&', '&', ['state', '=', 'paid'],
                    ['payment_date', '>=', from], ['payment_date', '<=', to],
                    ['state', '=', 'unpaid']
                );
            } else {
                domain.push(['date', '>=', from], ['date', '<=', to]);
            }
        };

        const applyYearMonth = (year, month) => {
            if (model === 'subscription') {
                domain.push(['year', '=', String(year)]);
                if (month) domain.push(['month', '=', String(month)]);
            } else {
                const lastDay = new Date(year, month || 12, 0).getDate();
                const mStr   = month ? String(month).padStart(2, '0') : null;
                domain.push(['date', '>=', mStr ? `${year}-${mStr}-01` : `${year}-01-01`]);
                domain.push(['date', '<=', mStr ? `${year}-${mStr}-${lastDay}` : `${year}-12-31`]);
            }
        };

        if (p === 'today') {
            applyDateRange(fmt(today), fmt(today));
        } else if (p === 'week') {
            const from = new Date(today); from.setDate(from.getDate() - 6);
            applyDateRange(fmt(from), fmt(today));
        } else if (p === 'last_30') {
            const from = new Date(today); from.setDate(from.getDate() - 30);
            applyDateRange(fmt(from), fmt(today));
        } else if (p === 'last_90') {
            const from = new Date(today); from.setDate(from.getDate() - 90);
            applyDateRange(fmt(from), fmt(today));
        } else if (p === 'quarter') {
            const qm    = Math.floor(today.getMonth() / 3) * 3;
            const from  = new Date(today.getFullYear(), qm, 1);
            const to    = new Date(today.getFullYear(), qm + 3, 0);
            applyDateRange(fmt(from), fmt(to));
        } else if (p === 'month' || p === 'this_month') {
            applyYearMonth(today.getFullYear(), today.getMonth() + 1);
        } else if (p === 'last_month') {
            const d = new Date(today.getFullYear(), today.getMonth() - 1, 1);
            applyYearMonth(d.getFullYear(), d.getMonth() + 1);
        } else if (p === 'year') {
            applyYearMonth(today.getFullYear(), null);
        } else if (p === 'q1') {
            applyDateRange(`${yr}-01-01`, `${yr}-03-31`);
        } else if (p === 'q2') {
            applyDateRange(`${yr}-04-01`, `${yr}-06-30`);
        } else if (p === 'q3') {
            applyDateRange(`${yr}-07-01`, `${yr}-09-30`);
        } else if (p === 'q4') {
            applyDateRange(`${yr}-10-01`, `${yr}-12-31`);
        } else if (/^([1-9]|1[0-2])$/.test(p)) {
            applyYearMonth(yr, parseInt(p));
        } else if (p === 'custom' && this.state.dateFrom && this.state.dateTo) {
            applyDateRange(this.state.dateFrom, this.state.dateTo);
        } else if (p === 'all') {
            // No date restriction – just tower filter applied above
        } else {
            // Default fallback: current month
            applyYearMonth(today.getFullYear(), today.getMonth() + 1);
        }

        return domain;
    }

    openTowers() {
        this._doAction({
            type: 'ir.actions.act_window',
            name: 'Towers | الأبراج',
            res_model: 'nahj.tower',
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            domain: this._buildFilterDomain('tower'),
        });
    }

    openUnits() {
        this._doAction({
            type: 'ir.actions.act_window',
            name: 'Units | الوحدات',
            res_model: 'nahj.unit',
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            domain: this._buildFilterDomain('unit'),
        });
    }

    openResidents() {
        // Residents are linked via their unit; filter by tower if selected
        const domain = this.state.selectedTower
            ? [['unit_ids.tower_id', '=', this.state.selectedTower]]
            : [];
        this._doAction({
            type: 'ir.actions.act_window',
            name: 'Residents | السكان',
            res_model: 'nahj.resident',
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            domain,
        });
    }

    openSubscriptions() {
        this._doAction({
            type: 'ir.actions.act_window',
            name: 'Subscriptions | الاشتراكات',
            res_model: 'nahj.subscription',
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            domain: this._buildFilterDomain('subscription'),
        });
    }

    openPaidSubscriptions() {
        this._doAction({
            type: 'ir.actions.act_window',
            name: 'Paid Subscriptions | الاشتراكات المدفوعة',
            res_model: 'nahj.subscription',
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            domain: this._buildFilterDomain('subscription', [['state', '=', 'paid']]),
        });
    }

    openExpenses() {
        this._doAction({
            type: 'ir.actions.act_window',
            name: 'Expenses | المصاريف',
            res_model: 'nahj.expense',
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            domain: this._buildFilterDomain('expense'),
        });
    }

    /** Sum of all paid subscriptions – used to compute per-method percentages */
    totalPaid() {
        const stats = this.state.data.payment_method_stats || [];
        return stats.reduce((s, pm) => s + (pm.amount || 0), 0);
    }

    openUnpaid() {
        this._doAction({
            type: 'ir.actions.act_window',
            name: 'Overdue Subscriptions | اشتراكات متأخرة',
            res_model: 'nahj.subscription',
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            domain: this._buildFilterDomain('subscription', [['state', '=', 'unpaid']]),
        });
    }

    // ── Helpers exposed to template ────────────────────────────────────────
    fmt(v)      { return formatMoney(v); }
    month(m)    { return MONTHS[m] || m; }
    get today() {
        const d = new Date();
        return d.toLocaleDateString('ar-EG', {
            weekday:'long', year:'numeric', month:'long', day:'numeric'
        });
    }
    get availableYears() {
        const base = (this.state.data.available_years) || [];
        if (base.length) return base;
        const yr = new Date().getFullYear();
        return [yr, yr-1, yr-2, yr-3, yr-4, yr-5];
    }

    /** Human-readable label for the active period – shown in Row 2 KPI cards */
    get periodLabel() {
        const p  = this.state.selectedPeriod;
        const yr = this.state.selectedYear || new Date().getFullYear();
        const MN = {
            '1':'يناير','2':'فبراير','3':'مارس','4':'أبريل',
            '5':'مايو','6':'يونيو','7':'يوليو','8':'أغسطس',
            '9':'سبتمبر','10':'أكتوبر','11':'نوفمبر','12':'ديسمبر',
        };
        if (p === 'month' || p === 'this_month') return 'هذا الشهر';
        if (p === 'last_month')  return 'الشهر الماضي';
        if (p === 'today')       return 'اليوم';
        if (p === 'week')        return 'هذا الأسبوع';
        if (p === 'last_30')     return 'آخر 30 يوم';
        if (p === 'last_90')     return 'آخر 90 يوم';
        if (p === 'quarter')     return 'هذا الربع';
        if (p === 'year')        return 'هذا العام ' + yr;
        if (p === 'q1')          return 'ربع 1 – ' + yr;
        if (p === 'q2')          return 'ربع 2 – ' + yr;
        if (p === 'q3')          return 'ربع 3 – ' + yr;
        if (p === 'q4')          return 'ربع 4 – ' + yr;
        if (p === 'custom')      return 'فترة مخصصة';
        if (/^([1-9]|1[0-2])$/.test(p)) return (MN[p] || p) + ' ' + yr;
        return 'الفترة المحددة';
    }
}

registry.category("actions").add("nahj_tower_dashboard", NahjDashboard);
