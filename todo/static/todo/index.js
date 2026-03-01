(() => {
    // Parse the server-provided JSON config and abort silently if unavailable.
    const getCookie = (name) => {
        const prefix = `${name}=`;
        return document.cookie
            .split(";")
            .map((entry) => entry.trim())
            .find((entry) => entry.startsWith(prefix))
            ?.slice(prefix.length) || "";
    };

    const cloneTemplate = (templateId) => {
        // Row/action markup lives in <template> tags in HTML; clone here so we
        // avoid building dynamic HTML strings in JS.
        const template = document.getElementById(templateId);
        if (!(template instanceof HTMLTemplateElement)) {
            return null;
        }
        const firstElement = template.content.firstElementChild;
        if (!(firstElement instanceof HTMLElement)) {
            return null;
        }
        return firstElement.cloneNode(true);
    };

    const configScript = document.getElementById("todo-ui-config");
    if (!(configScript instanceof HTMLScriptElement)) {
        return;
    }

    let uiConfig;
    try {
        uiConfig = JSON.parse(configScript.textContent || "{}");
    } catch (_error) {
        return;
    }

    const csrfToken = getCookie("csrftoken");
    const i18n = uiConfig.i18n || {};
    const urls = uiConfig.urls || {};

    const setFieldText = (rowElement, fieldName, value) => {
        const cell = rowElement.querySelector(`[data-field="${fieldName}"]`);
        if (!(cell instanceof HTMLElement)) {
            return;
        }
        cell.textContent = value ? String(value) : i18n.fallback_value;
    };

    const createActionForm = (actionUrl, label, buttonClass) => {
        const form = cloneTemplate("todo-template-action-form");
        if (!(form instanceof HTMLFormElement)) {
            return null;
        }
        form.action = actionUrl;
        const csrfInput = form.querySelector("input[name='csrfmiddlewaretoken']");
        if (csrfInput instanceof HTMLInputElement) {
            csrfInput.value = csrfToken;
        }
        const button = form.querySelector("button");
        if (button instanceof HTMLButtonElement) {
            button.classList.add(buttonClass);
            button.textContent = label;
        }
        return form;
    };

    const appendActions = (rowElement, item) => {
        const actionCell = rowElement.querySelector('[data-field="actions"]');
        if (!(actionCell instanceof HTMLElement)) {
            return;
        }

        const actions = [];
        // The API already returns action booleans; respect them directly.
        if (item.can_unclaim) {
            actions.push(
                createActionForm(item.urls.unclaim, i18n.unclaim, "btn-outline-secondary")
            );
        } else if (item.can_claim) {
            actions.push(
                createActionForm(item.urls.claim, i18n.claim, "btn-outline-secondary")
            );
        }
        if (item.can_done) {
            actions.push(createActionForm(item.urls.done, i18n.done, "btn-success"));
        }
        if (item.can_delete) {
            actions.push(createActionForm(item.urls.delete, i18n.delete, "btn-danger"));
        }

        for (const action of actions) {
            if (action) {
                actionCell.append(action);
            }
        }
    };

    const buildRow = (templateId, fields, item) => {
        const row = cloneTemplate(templateId);
        if (!(row instanceof HTMLTableRowElement)) {
            return null;
        }
        for (const field of fields) {
            setFieldText(row, field, item[field]);
        }
        appendActions(row, item);
        return row;
    };

    const setBodyMessage = (body, colCount, message, isError = false) => {
        body.replaceChildren();
        const row = cloneTemplate("todo-template-message-row");
        if (!(row instanceof HTMLTableRowElement)) {
            return;
        }
        const cell = row.querySelector("td");
        if (cell instanceof HTMLTableCellElement) {
            cell.colSpan = colCount;
            cell.classList.add(isError ? "text-danger" : "text-muted");
            cell.textContent = message;
        }
        body.append(row);
    };

    const listConfigs = {
        group: {
            url: urls.group,
            bodyId: "todo-group-body",
            pagerId: "todo-group-pager",
            metaId: "todo-group-page-meta",
            colCount: 9,
            emptyText: i18n.no_group_items,
            rowTemplateId: "todo-template-group-row",
            rowFields: [
                "group_name",
                "title",
                "description",
                "created_at_display",
                "created_by",
                "status_display",
                "claimed_by",
                "done_by",
            ],
        },
        personal: {
            url: urls.personal,
            bodyId: "todo-personal-body",
            pagerId: "todo-personal-pager",
            metaId: "todo-personal-page-meta",
            colCount: 7,
            emptyText: i18n.no_personal_items,
            rowTemplateId: "todo-template-personal-row",
            rowFields: [
                "title",
                "description",
                "created_at_display",
                "status_display",
                "claimed_by",
                "done_by",
            ],
        },
    };

    if (uiConfig.has_personal_other && document.getElementById("todo-personal-other-card")) {
        // Personal-other list only exists for full-access users.
        listConfigs.personalOther = {
            url: urls.personal_other,
            bodyId: "todo-personal-other-body",
            pagerId: "todo-personal-other-pager",
            metaId: "todo-personal-other-page-meta",
            colCount: 8,
            emptyText: i18n.no_other_personal_items,
            rowTemplateId: "todo-template-personal-other-row",
            rowFields: [
                "title",
                "description",
                "created_at_display",
                "created_by",
                "status_display",
                "claimed_by",
                "done_by",
            ],
        };
    }

    const renderPager = (listKey, data) => {
        const config = listConfigs[listKey];
        const pager = document.getElementById(config.pagerId);
        const meta = document.getElementById(config.metaId);

        if (!(pager instanceof HTMLElement) || !(meta instanceof HTMLElement)) {
            return;
        }

        meta.textContent = i18n.page_meta
            .replace("%(page)s", String(data.page))
            .replace("%(total_pages)s", String(data.total_pages))
            .replace("%(total_items)s", String(data.total_items));

        pager.replaceChildren();
        const prevButton = document.createElement("button");
        prevButton.type = "button";
        prevButton.className = "btn btn-sm btn-outline-secondary";
        prevButton.dataset.list = listKey;
        prevButton.dataset.page = String(data.page - 1);
        prevButton.textContent = i18n.prev;
        prevButton.disabled = !data.has_prev;

        const nextButton = document.createElement("button");
        nextButton.type = "button";
        nextButton.className = "btn btn-sm btn-outline-secondary";
        nextButton.dataset.list = listKey;
        nextButton.dataset.page = String(data.page + 1);
        nextButton.textContent = i18n.next;
        nextButton.disabled = !data.has_next;

        pager.append(prevButton, nextButton);
    };

    const clearPagingUi = (listKey) => {
        const config = listConfigs[listKey];
        const pager = document.getElementById(config.pagerId);
        const meta = document.getElementById(config.metaId);
        if (pager instanceof HTMLElement) {
            pager.replaceChildren();
        }
        if (meta instanceof HTMLElement) {
            meta.textContent = "";
        }
    };

    const loadList = async (listKey, page = 1) => {
        const config = listConfigs[listKey];
        const body = document.getElementById(config.bodyId);
        if (!(body instanceof HTMLTableSectionElement)) {
            return;
        }

        setBodyMessage(body, config.colCount, i18n.loading_items);

        const url = new URL(config.url, window.location.origin);
        url.searchParams.set("page", String(page));

        let response;
        try {
            // Same-origin call keeps session auth/cookies and CSRF model intact.
            response = await fetch(url.toString(), {
                credentials: "same-origin",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                },
            });
        } catch (_error) {
            clearPagingUi(listKey);
            setBodyMessage(body, config.colCount, i18n.failed_load_items, true);
            return;
        }

        if (!response.ok) {
            clearPagingUi(listKey);
            setBodyMessage(
                body,
                config.colCount,
                i18n.failed_load_items_status.replace("%(status)s", String(response.status)),
                true
            );
            return;
        }

        const data = await response.json();
        if (!data.results.length) {
            setBodyMessage(body, config.colCount, config.emptyText);
            renderPager(listKey, data);
            return;
        }

        body.replaceChildren();
        for (const item of data.results) {
            const row = buildRow(config.rowTemplateId, config.rowFields, item);
            if (row) {
                body.append(row);
            }
        }

        renderPager(listKey, data);
    };

    document.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof HTMLButtonElement)) {
            return;
        }
        if (!target.dataset.list || !target.dataset.page) {
            return;
        }
        event.preventDefault();
        const listKey = target.dataset.list;
        const nextPage = Number(target.dataset.page);
        if (!listConfigs[listKey] || Number.isNaN(nextPage) || nextPage < 1) {
            return;
        }
        loadList(listKey, nextPage);
    });

    // Initial hydration after the form/page shell has rendered.
    Object.keys(listConfigs).forEach((key) => {
        loadList(key, 1);
    });
})();
