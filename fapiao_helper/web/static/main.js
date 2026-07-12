/* 发票助手 - 前端交互 */

// ============ 工具函数 ============
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const STATUS = (s) => `status-${s || 'pending'}`;

function setStatus(msg, isError = false) {
    const el = $('#status-line');
    if (el) {
        el.textContent = msg;
        el.style.color = isError ? '#e74c3c' : '#555';
    }
}

async function api(url, opts = {}) {
    const res = await fetch(url, opts);
    const ctype = res.headers.get('content-type') || '';
    if (ctype.includes('application/json')) {
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
        return data;
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res;
}

function fmtMoney(v) {
    const n = Number(v || 0);
    return n.toFixed(2);
}

// ============ Tab 切换 ============
function initTabs() {
    $$('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            $$('.tab-btn').forEach(b => b.classList.remove('active'));
            $$('.tab-panel').forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            const target = $('#' + btn.dataset.tab);
            if (target) target.classList.add('active');
            // 切到库时自动加载
            if (btn.dataset.tab === 'tab-library') loadInvoices();
            if (btn.dataset.tab === 'tab-debug') loadLogs();
        });
    });
}

// ============ 导入:拖拽 + 上传 ============
let pendingFiles = [];

function initUpload() {
    const dz = $('#drop-zone');
    const input = $('#file-input');
    const list = $('#file-list');
    const uploadBtn = $('#upload-btn');

    if (!dz) return;

    dz.addEventListener('click', () => input.click());
    input.addEventListener('change', () => addFiles(input.files));

    ['dragover', 'dragenter'].forEach(ev =>
        dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.add('dragover'); })
    );
    ['dragleave', 'drop'].forEach(ev =>
        dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.remove('dragover'); })
    );
    dz.addEventListener('drop', e => {
        if (e.dataTransfer && e.dataTransfer.files) addFiles(e.dataTransfer.files);
    });

    function addFiles(fileList) {
        Array.from(fileList).forEach(f => pendingFiles.push(f));
        renderList();
    }

    function renderList() {
        list.innerHTML = '';
        pendingFiles.forEach((f, i) => {
            const li = document.createElement('li');
            li.textContent = `${i + 1}. ${f.name} (${(f.size / 1024).toFixed(1)} KB)`;
            const rm = document.createElement('button');
            rm.textContent = '移除';
            rm.className = 'ghost';
            rm.style.marginLeft = '8px';
            rm.addEventListener('click', () => { pendingFiles.splice(i, 1); renderList(); });
            li.appendChild(rm);
            list.appendChild(li);
        });
        uploadBtn.disabled = pendingFiles.length === 0;
    }

    uploadBtn.addEventListener('click', async () => {
        if (!pendingFiles.length) return;
        const fd = new FormData();
        pendingFiles.forEach(f => fd.append('files', f));
        fd.append('default_project', $('#default-project').value || '');
        uploadBtn.disabled = true;
        $('#upload-msg').textContent = '上传中...';
        try {
            const data = await api('/api/invoices/upload', { method: 'POST', body: fd });
            $('#upload-msg').textContent = `已创建任务 #${data.job_id},共 ${data.count} 个文件`;
            pendingFiles = [];
            renderList();
            loadJobs();
            setStatus(`任务 #${data.job_id} 处理中`);
        } catch (e) {
            $('#upload-msg').textContent = '失败: ' + e.message;
            $('#upload-msg').classList.add('error');
        } finally {
            uploadBtn.disabled = false;
        }
    });

    $('#refresh-jobs')?.addEventListener('click', loadJobs);
}

async function loadJobs() {
    const tbody = $('#jobs-table tbody');
    if (!tbody) return;
    try {
        const jobs = await api('/api/jobs');
        tbody.innerHTML = '';
        jobs.forEach(j => {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td>${j.id}</td>
                <td class="${STATUS(j.status)}">${j.status || ''}</td>
                <td>${j.done || 0}/${j.total || 0}</td>
                <td>${j.failed || 0}</td>
                <td>${j.created_at || ''}</td>`;
            tbody.appendChild(tr);
        });
    } catch (e) {
        setStatus('加载任务失败: ' + e.message, true);
    }
}

// ============ 库:加载/筛选/编辑 ============
let currentPage = 1;
const PAGE_SIZE = 100;

async function loadProjects() {
    try {
        const projects = await api('/api/projects');
        const sel = $('#f-project');
        if (!sel) return;
        const cur = sel.value;
        sel.innerHTML = '<option value="">全部项目</option>';
        projects.forEach(p => {
            const o = document.createElement('option');
            o.value = p.name; o.textContent = p.name;
            sel.appendChild(o);
        });
        sel.value = cur;
    } catch (e) { /* 忽略 */ }
}

async function loadInvoices() {
    await loadProjects();
    const params = new URLSearchParams();
    const status = $('#f-status').value; if (status) params.set('status', status);
    const project = $('#f-project').value; if (project) params.set('project', project);
    const month = $('#f-month').value; if (month) params.set('month', month);
    const q = $('#f-q').value; if (q) params.set('q', q);
    params.set('page', currentPage);
    try {
        const data = await api('/api/invoices?' + params.toString());
        renderInvoices(data.items || []);
        $('#page-info').textContent = `第 ${data.page} 页 / 共 ${Math.max(1, Math.ceil(data.total / data.page_size))} 页 (${data.total})`;
        setStatus(`已加载 ${data.items.length} 条,共 ${data.total}`);
    } catch (e) {
        setStatus('加载发票失败: ' + e.message, true);
    }
}

function renderInvoices(items) {
    const tbody = $('#invoices-table tbody');
    tbody.innerHTML = '';
    let sumAmt = 0, sumTax = 0, sumTotal = 0;
    items.forEach(inv => {
        sumAmt += Number(inv.amount || 0);
        sumTax += Number(inv.tax || 0);
        sumTotal += Number(inv.total || 0);
        const tr = document.createElement('tr');
        tr.dataset.id = inv.id;
        tr.innerHTML = `
            <td><input type="checkbox" class="row-check" value="${inv.id}"></td>
            <td>${inv.id}</td>
            <td contenteditable="true" data-field="invoice_no">${inv.invoice_no || ''}</td>
            <td contenteditable="true" data-field="invoice_date">${inv.invoice_date || ''}</td>
            <td contenteditable="true" data-field="seller">${inv.seller || ''}</td>
            <td contenteditable="true" data-field="buyer">${inv.buyer || ''}</td>
            <td contenteditable="true" data-field="amount">${inv.amount || ''}</td>
            <td contenteditable="true" data-field="tax">${inv.tax || ''}</td>
            <td contenteditable="true" data-field="total">${inv.total || ''}</td>
            <td contenteditable="true" data-field="category">${inv.category || ''}</td>
            <td contenteditable="true" data-field="project">${inv.project || ''}</td>
            <td class="${STATUS(inv.status)}" contenteditable="true" data-field="status">${inv.status || ''}</td>
            <td>${inv.needs_review ? '是' : '否'}</td>
            <td>
                <button class="ghost save-row">保存</button>
                <button class="ghost re-recog">重识</button>
            </td>`;
        tbody.appendChild(tr);
    });
    $('#sum-amount').textContent = fmtMoney(sumAmt);
    $('#sum-tax').textContent = fmtMoney(sumTax);
    $('#sum-total').textContent = fmtMoney(sumTotal);
    bindRowEvents();
}

function bindRowEvents() {
    $$('.save-row').forEach(btn => {
        btn.addEventListener('click', async () => {
            const tr = btn.closest('tr');
            const id = tr.dataset.id;
            const fields = {};
            $$('[data-field]', tr).forEach(td => {
                fields[td.dataset.field] = td.textContent.trim();
            });
            // 数值字段转 number
            ['amount', 'tax', 'total'].forEach(k => {
                if (fields[k] !== '') fields[k] = Number(fields[k]);
            });
            try {
                await api(`/api/invoices/${id}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(fields),
                });
                setStatus(`发票 #${id} 已保存`);
                loadInvoices();
            } catch (e) {
                setStatus('保存失败: ' + e.message, true);
            }
        });
    });

    $$('.re-recog').forEach(btn => {
        btn.addEventListener('click', async () => {
            const tr = btn.closest('tr');
            const id = tr.dataset.id;
            setStatus(`正在重新识别 #${id}...`);
            try {
                const data = await api(`/api/invoices/${id}/re-recognize`, { method: 'POST' });
                setStatus(`#${id} 重识别完成,需复核: ${data.needs_review}`);
                loadInvoices();
            } catch (e) {
                setStatus('重识别失败: ' + e.message, true);
            }
        });
    });
}

function initLibrary() {
    $('#lib-search')?.addEventListener('click', () => { currentPage = 1; loadInvoices(); });
    $('#prev-page')?.addEventListener('click', () => { if (currentPage > 1) { currentPage--; loadInvoices(); } });
    $('#next-page')?.addEventListener('click', () => { currentPage++; loadInvoices(); });
    $('#select-all')?.addEventListener('change', e => {
        $$('.row-check').forEach(c => c.checked = e.target.checked);
    });
}

// ============ 导出 ============
function initExport() {
    $('#export-xlsx')?.addEventListener('click', async () => {
        const mode = $$('input[name="xlsx-mode"]:checked')[0]?.value;
        let body;
        if (mode === 'selected') {
            const ids = $$('.row-check:checked').map(c => Number(c.value));
            if (!ids.length) { setStatus('请先在库中勾选发票', true); return; }
            body = { selected_ids: ids };
        } else {
            const flt = {};
            const s = $('#f-status').value; if (s) flt.status = s;
            const p = $('#f-project').value; if (p) flt.project = p;
            const m = $('#f-month').value; if (m) flt.month = m;
            const q = $('#f-q').value; if (q) flt.q = q;
            body = { filter: flt };
        }
        await download('/api/export/xlsx', body, 'invoices.xlsx');
    });

    $('#export-pdf')?.addEventListener('click', async () => {
        const ids = $$('.row-check:checked').map(c => Number(c.value));
        if (!ids.length) { setStatus('请先在库中勾选发票', true); return; }
        const cover_meta = { title: $('#cover-title').value || '发票汇总' };
        await download('/api/export/pdf-merge', { selected_ids: ids, cover_meta }, 'merged.pdf');
    });
}

async function download(url, body, fallbackName) {
    const msg = $('#export-msg');
    if (msg) { msg.textContent = '生成中...'; msg.classList.remove('error'); }
    try {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!res.ok) {
            const txt = await res.text();
            throw new Error(txt || `HTTP ${res.status}`);
        }
        const blob = await res.blob();
        const disposition = res.headers.get('content-disposition') || '';
        const m = /filename="?([^";]+)"?/.exec(disposition);
        const name = m ? m[1] : fallbackName;
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = name;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(a.href);
        if (msg) msg.textContent = '已下载: ' + name;
        setStatus('导出完成');
    } catch (e) {
        if (msg) { msg.textContent = '失败: ' + e.message; msg.classList.add('error'); }
        setStatus('导出失败: ' + e.message, true);
    }
}

// ============ 调试 ============
function initDebug() {
    $('#load-logs')?.addEventListener('click', loadLogs);
    $('#load-invoice-debug')?.addEventListener('click', async () => {
        const id = $('#invoice-debug-id').value;
        if (!id) return;
        try {
            const data = await api(`/debug/invoice/${id}`);
            $('#debug-output').textContent = JSON.stringify(data, null, 2);
        } catch (e) {
            $('#debug-output').textContent = '错误: ' + e.message;
        }
    });
}

async function loadLogs() {
    try {
        const data = await api('/debug');
        $('#debug-output').textContent = JSON.stringify(data, null, 2);
    } catch (e) {
        $('#debug-output').textContent = '错误: ' + e.message;
    }
}

// ============ 初始化 ============
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initUpload();
    initLibrary();
    initExport();
    initDebug();
    loadJobs();
    setStatus('就绪');
});
