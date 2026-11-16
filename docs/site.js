'use strict';

    "use strict";

    const byId = (id) => document.getElementById(id);

    const DATA_KEY = "hzo_research_local_candidates_v2";
    const NOTES_KEY = "hzo_research_notes_v2";

    let baseData = [];
    let localData = [];
    let visibleLimit = 25;
    let chartAxis = "hzo_nm";
    let selectedElectrodes = null;
    let dataLoadFinished = false;

    function finiteNumber(value) {
      if (value === null || value === undefined || value === "") {
        return null;
      }

      if (typeof value === "boolean") {
        return null;
      }

      const number = Number(value);
      return Number.isFinite(number) ? number : null;
    }

    function display(value) {
      return value === null || value === undefined || value === ""
        ? "—"
        : String(value);
    }

    function numericLabel(value) {
      const number = finiteNumber(value);

      if (number === null) return "—";

      return number.toLocaleString("en-US", {
        maximumFractionDigits: 4
      });
    }

    function allData() {
      return baseData.concat(localData);
    }

    function isTwoPrCandidate(row) {
      return row.metric === "2Pr" && finiteNumber(row.two_pr) !== null;
    }

    function safeURL(value) {
      if (!value) return null;

      try {
        const url = new URL(String(value));

        return ["https:", "http:"].includes(url.protocol)
          ? url.href
          : null;
      } catch {
        return null;
      }
    }

    function normalizeRecord(raw, sourceName, index, local) {
      if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
        throw new Error("각 기록은 JSON 객체여야 합니다.");
      }

      const result = {};

      const textFields = [
        "record_id",
        "source_file",
        "source_sheet",
        "sample_id",
        "paper",
        "doi",
        "source_url",
        "source_locator",
        "metric",
        "structure",
        "composition",
        "top",
        "bottom",
        "anneal_type",
        "atmosphere",
        "measurement_method",
        "measurement_state",
        "deposition",
        "verification",
        "notes", "possible_overlap", "sample_group", "sheet_membership", "il_material", "il_position",
        "endurance_relation", "endurance_definition", "voltage_definition", "cycling_voltage_definition",
        "cycle_definition", "measurement_definition", "numeric_confidence", "evidence_level", "raw_json"
      ];

      const numericFields = [
        "two_pr",
        "hzo_nm",
        "top_nm",
        "bottom_nm",
        "top_interlayer_nm",
        "bottom_interlayer_nm",
        "anneal_c",
        "anneal_s",
        "voltage_v",
        "wake_cycles",
        "ald_c",
        "pulse_s",
        "frequency_hz",
        "source_row", "pr", "two_pr_lower_bound", "endurance_cycles", "cycling_voltage_v",
        "cycling_field_mv_cm", "cycling_frequency_hz", "cycling_pulse_s", "cycling_temperature_c",
        "measurement_temperature_k", "end_two_pr", "retention_pct", "il_nm", "hf_fraction", "memory_window_v", "threshold_shift_v"
      ];

      textFields.forEach((field) => {
        const value = raw[field];

        result[field] =
          value === null || value === undefined
            ? null
            : String(value).trim();
      });

      numericFields.forEach((field) => {
        result[field] = finiteNumber(raw[field]);
      });

      result.source_file =
        result.source_file || sourceName || "출처 미기재";

      result.sample_id =
        result.sample_id || "미기재-" + (index + 1);

      result.metric = result.metric || "정의 미확인";
      result.review_status = "pending";
      if (result.pr !== null || result.two_pr_lower_bound !== null || /CONFLICT/i.test(result.measurement_state || "")) {
        result.metric = result.pr !== null ? "Pr" : result.two_pr_lower_bound !== null ? "2Pr lower bound" : "Pr/2Pr conflict";
        result.two_pr = null;
      }

      if (local) {
        result.verification = "브라우저 추가 · 원문 검토 전 · 미승인";
        result.source_file = "브라우저 추가 / " + sourceName;
      }

      return result;
    }

    function saveLocalData() {
      localStorage.setItem(DATA_KEY, JSON.stringify(localData));
    }

    function restoreLocalData() {
      try {
        const stored = JSON.parse(localStorage.getItem(DATA_KEY) || "[]");

        if (Array.isArray(stored)) {
          localData = stored.filter(
            (row) => row && typeof row === "object" && !Array.isArray(row)
          );

          localData.forEach((row) => {
            row.verification = "브라우저 추가 · 원문 검토 전 · 미승인";
          });
        }
      } catch {
        localData = [];
        byId("importStatus").textContent =
          "기존 브라우저 저장 자료를 읽지 못했습니다.";
      }
    }

    function rebuildFilterOptions() {
      const data = allData();
      const selectedStructure = byId("structureFilter").value;
      byId("structureFilter").replaceChildren(new Option("전체 구조 (산점도는 구조 선택 후 표시)", ""));
      [...new Set(data.map(r => r.structure || "미확인"))].sort().forEach(v => byId("structureFilter").add(new Option(v,v)));
      byId("structureFilter").value = selectedStructure;
      const previousSource = byId("sourceFilter").value;
      const previousAnneal = byId("annealFilter").value;

      byId("sourceFilter").replaceChildren();
      byId("annealFilter").replaceChildren();

      function addOption(select, value, label) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = label;
        select.append(option);
      }

      addOption(byId("sourceFilter"), "", "전체 출처");
      addOption(byId("annealFilter"), "", "전체 열처리");
      addOption(byId("annealFilter"), "__unknown__", "미확인");

      const sources = [...new Set(
        data.map((row) => row.source_file).filter(Boolean)
      )].sort();

      const anneals = [...new Set(
        data.map((row) => row.anneal_type).filter(Boolean)
      )].sort();

      sources.forEach((source) => {
        addOption(byId("sourceFilter"), source, source);
      });

      anneals.forEach((anneal) => {
        addOption(byId("annealFilter"), anneal, anneal);
      });

      if (sources.includes(previousSource)) {
        byId("sourceFilter").value = previousSource;
      }

      if (anneals.includes(previousAnneal) ||
          previousAnneal === "__unknown__") {
        byId("annealFilter").value = previousAnneal;
      }
    }

    function updateStats() {
      const data = allData();

      byId("candidateCount").textContent =
        data.filter(isTwoPrCandidate).length;

      byId("recordCount").textContent = data.length;
    }

    function getFilteredRows() {
      const query = byId("searchInput").value.trim().toLowerCase();
      const source = byId("sourceFilter").value;
      const anneal = byId("annealFilter").value;
      const onlyTwoPr = byId("onlyTwoPr").checked;

      return allData().filter((row) => {
        const structure = byId("structureFilter").value;
        const metric = byId("metricFilter").value;
        if (structure && (row.structure || "미확인") !== structure) return false;
        if (metric === "endurance" ? row.endurance_cycles === null : metric && row.metric !== metric) return false;
        if (source && row.source_file !== source) return false;

        if (anneal === "__unknown__" && row.anneal_type) return false;

        if (
          anneal &&
          anneal !== "__unknown__" &&
          row.anneal_type !== anneal
        ) {
          return false;
        }

        if (onlyTwoPr && !isTwoPrCandidate(row)) return false;

        if (selectedElectrodes) {
          if (row.top !== selectedElectrodes.top) return false;
          if (row.bottom !== selectedElectrodes.bottom) return false;
        }

        if (query) {
          const searchableFields = [
            "sample_id", "paper", "doi", "top", "bottom",
            "source_file", "notes", "source_locator"
          ];

          const matched = searchableFields.some((field) => {
            return String(row[field] || "")
              .toLowerCase()
              .includes(query);
          });

          if (!matched) return false;
        }

        return true;
      });
    }

    function appendCell(tr, value) {
      const td = document.createElement("td");
      td.textContent = display(value);
      tr.append(td);
      return td;
    }

    function renderTable(rows) {
      byId("dataRows").replaceChildren();

      for (const row of rows.slice(0, visibleLimit)) {
        const tr = document.createElement("tr");

        const sampleCell = appendCell(tr, row.sample_id);
        const source = document.createElement("small");
        source.textContent = display(row.source_file);
        sampleCell.append(source);
        const details = document.createElement("details");
        const summary = document.createElement("summary"); summary.textContent = (row.structure || "미확인") + " · " + row.metric + " · 조건/원본 보기";
        const description = document.createElement("div");
        const fields = ["possible_overlap","source_sheet","source_row","source_locator","sample_group","sheet_membership","metric","pr","two_pr_lower_bound","measurement_definition","measurement_method","measurement_state","wake_cycles","voltage_v","voltage_definition","pulse_s","frequency_hz","endurance_cycles","endurance_relation","endurance_definition","cycling_voltage_v","cycling_voltage_definition","cycling_pulse_s","cycling_frequency_hz","il_material","il_nm","il_position","numeric_confidence","evidence_level","notes","raw_json"];
        description.textContent = fields.map(k => k + ": " + display(row[k])).join("\n"); description.style.whiteSpace = "pre-wrap";
        details.append(summary,description); sampleCell.append(details);

        appendCell(
          tr,
          isTwoPrCandidate(row)
            ? numericLabel(row.two_pr)
            : "—"
        );

        appendCell(tr, numericLabel(row.hzo_nm));

        appendCell(
          tr,
          display(row.top) + " / " + display(row.bottom)
        );

        appendCell(tr, row.anneal_type || "미확인");
        appendCell(tr, numericLabel(row.anneal_c));
        appendCell(tr, row.verification || "원문 검토 전 · 미승인");

        const sourceCell = appendCell(tr, "");

        let url = null;

        if (row.doi && /^10\.\d{4,9}\/\S+$/i.test(row.doi)) {
          url = safeURL("https://doi.org/" + row.doi);
        }

        url = url || safeURL(row.source_url);

        if (url) {
          sourceCell.textContent = "";

          const link = document.createElement("a");
          link.href = url;
          link.textContent = "원문 ↗";
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          sourceCell.append(link);
        }

        byId("dataRows").append(tr);
      }

      if (!rows.length) {
        const tr = document.createElement("tr");
        const td = document.createElement("td");

        td.colSpan = 8;
        td.textContent =
          "조건에 맞는 기록이 없습니다. 필터 초기화를 눌러 확인하세요.";

        tr.append(td);
        byId("dataRows").append(tr);
      }

      byId("showMore").hidden = visibleLimit >= rows.length;

      byId("rowCount").textContent =
        "검색 결과 " + rows.length + "행 · 숫자 2Pr 후보 " +
        rows.filter(isTwoPrCandidate).length + "행";
    }

    function svgElement(tag, attributes, text) {
      const node = document.createElementNS(
        "http://www.w3.org/2000/svg",
        tag
      );

      Object.entries(attributes).forEach(([key, value]) => {
        node.setAttribute(key, String(value));
      });

      if (text !== undefined) node.textContent = text;

      return node;
    }

    function renderChart(rows) {
      if (!byId("structureFilter").value) {
        byId("chart").replaceChildren();
        byId("chartSummary").textContent = "소자 구조를 선택하면 해당 구조의 2Pr 후보만 표시합니다. Pr·하한·충돌·Endurance는 2Pr 점값과 합치지 않습니다.";
        return;
      }
      const points = rows.filter((row) => {
        return isTwoPrCandidate(row) &&
          finiteNumber(row[chartAxis]) !== null;
      });

      const width = 900;
      const height = 330;
      const padding = { left: 55, right: 20, top: 25, bottom: 50 };
      const plotWidth = width - padding.left - padding.right;
      const plotHeight = height - padding.top - padding.bottom;

      const xValues = points.map((row) => finiteNumber(row[chartAxis]));
      const yValues = points.map((row) => finiteNumber(row.two_pr));

      const minX = Math.min(0, ...xValues);
      const minY = Math.min(0, ...yValues);
      const maxX = Math.max(1, ...xValues);
      const maxY = Math.max(1, ...yValues);

      const xRange = Math.max(1, maxX - minX) * 1.1;
      const yRange = Math.max(1, maxY - minY) * 1.1;

      const svg = svgElement("svg", {
        viewBox: "0 0 " + width + " " + height,
        role: "img",
        "aria-label": points.length + "개 문헌 2Pr 후보 산점도"
      });

      for (let tick = 0; tick <= 4; tick++) {
        const ratio = tick / 4;
        const y = padding.top + plotHeight * (1 - ratio);
        const x = padding.left + plotWidth * ratio;

        svg.append(svgElement("line", {
          x1: padding.left,
          x2: width - padding.right,
          y1: y,
          y2: y,
          class: "gridline"
        }));

        svg.append(svgElement("text", {
          x: padding.left - 10,
          y: y + 4,
          "text-anchor": "end",
          class: "tick"
        }, (minY + yRange * ratio).toFixed(0)));

        svg.append(svgElement("text", {
          x: x,
          y: height - padding.bottom + 22,
          "text-anchor": "middle",
          class: "tick"
        }, (minX + xRange * ratio).toFixed(
          chartAxis === "hzo_nm" ? 1 : 0
        )));
      }

      points.forEach((row) => {
        const x = padding.left +
          ((finiteNumber(row[chartAxis]) - minX) / xRange) * plotWidth;

        const y = padding.top + plotHeight -
          ((finiteNumber(row.two_pr) - minY) / yRange) * plotHeight;

        const circle = svgElement("circle", {
          cx: x,
          cy: y,
          r: 5.5,
          class: "point",
          tabindex: 0,
          fill: row.anneal_type === "RTA" ? "#7ae6c2" : "#8eb7ff",
          "aria-label":
            display(row.sample_id) + ": " +
            numericLabel(row.two_pr) + " μC/cm²"
        });

        circle.append(svgElement("title", {},
          display(row.sample_id) + "\n" +
          "2Pr: " + numericLabel(row.two_pr) + " μC/cm²\n" +
          "열처리: " + display(row.anneal_type) + "\n" +
          "DOI: " + display(row.doi) + "\n" +
          "원문 검토 및 학습 승인과 별개인 후보값"
        ));

        svg.append(circle);
      });

      svg.append(svgElement("text", {
        x: width / 2,
        y: height - 5,
        "text-anchor": "middle",
        class: "tick"
      }, chartAxis === "hzo_nm"
        ? "HZO 두께 (nm)"
        : "열처리 온도 (°C)"
      ));

      byId("chart").replaceChildren(svg);

      byId("chartSummary").textContent =
        "그래프 " + points.length + "행 표시 / 검색 " +
        rows.length + "행. 비교 축이 없거나 비2Pr인 기록은 " +
        "산점도에서 제외됩니다. 점 위에 마우스를 올리면 출처가 표시됩니다.";
    }

    function render() {
      const rows = getFilteredRows();

      updateStats();
      renderTable(rows);
      renderChart(rows);

      byId("electrodeFilterLabel").textContent =
        selectedElectrodes
          ? "전극 조건: " + selectedElectrodes.top +
            " / " + selectedElectrodes.bottom
          : "";
    }

    function resetFilters() {
      byId("searchInput").value = "";
      byId("sourceFilter").value = "";
      byId("annealFilter").value = "";
      byId("onlyTwoPr").checked = false;
      byId("structureFilter").value = "";
      byId("metricFilter").value = "";

      selectedElectrodes = null;
      visibleLimit = 25;

      render();
    }

    function optionalInputNumber(id) {
      return finiteNumber(byId(id).value);
    }

    function findExperiments() {
      const form = byId("processForm");

      if (!form.reportValidity()) return;

      const top = byId("topInput").value;
      const bottom = byId("bottomInput").value;

      byId("searchInput").value = "";
      byId("sourceFilter").value = "";
      byId("annealFilter").value = "RTA";
      byId("onlyTwoPr").checked = true;
      byId("structureFilter").value = byId("deviceStructure").value;

      /*
       * RTA가 아직 옵션에 없는 경우에도 조건을 정확히 적용할 수 있도록
       * 선택지를 추가합니다.
       */
      if (![...byId("annealFilter").options].some(
        (option) => option.value === "RTA"
      )) {
        const option = document.createElement("option");
        option.value = "RTA";
        option.textContent = "RTA";
        byId("annealFilter").append(option);
      }

      byId("annealFilter").value = "RTA";

      selectedElectrodes = { top, bottom };
      visibleLimit = 25;

      render();

      const count = getFilteredRows().length;
      const hzo = byId("hzoInput").value;
      const temperature = byId("temperatureInput").value;
      const time = byId("timeInput").value;
      const voltage = byId("voltageInput").value;

      const topInterlayer = optionalInputNumber("topInterlayerInput");
      const bottomInterlayer = optionalInputNumber("bottomInterlayerInput");

      let message =
        "입력 확인: " + top + " / HZO " + hzo + " nm / " + bottom +
        ", RTA " + temperature + " °C · " + time + " s" +
        ", 측정 " + voltage + " V. " +
        "아래 표에 같은 Top/Bottom 전극의 RTA 2Pr 후보 " +
        count + "행을 표시했습니다. " +
        "두께·온도·시간·전압이 모두 일치하는 결과나 AI 예측은 아닙니다.";

      if ((topInterlayer !== null && topInterlayer > 0) ||
          (bottomInterlayer !== null && bottomInterlayer > 0)) {
        message +=
          " 삽입층이 입력되었습니다. 이 조건은 Phase 1 기본 예측 범위 밖입니다.";
      }

      if (!dataLoadFinished) {
        message += " 기존 데이터가 아직 로딩 중일 수 있습니다.";
      }

      byId("conditionMessage").textContent = message;
      byId("conditionMessage").hidden = false;

      byId("data").scrollIntoView({
        behavior: "smooth",
        block: "start"
      });
    }

    function parseCSV(text) {
  /*
   * 제목·설명 행과 셀 내부 줄바꿈이 있는 CSV를 처리합니다.
   * 기존 정규화 CSV와 HZO 데이터셋 v3 형식을 지원합니다.
   * 값을 검증하거나 학습 승인하지는 않습니다.
   */

  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;

  text = text.replace(/^\uFEFF/, "");

  for (let i = 0; i < text.length; i++) {
    const char = text[i];

    if (char === '"') {
      if (quoted && text[i + 1] === '"') {
        field += '"';
        i++;
      } else {
        quoted = !quoted;
      }
    } else if (char === "," && !quoted) {
      row.push(field);
      field = "";
    } else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && text[i + 1] === "\n") {
        i++;
      }

      row.push(field);

      if (row.some(value => value.trim() !== "")) {
        rows.push(row);
      }

      row = [];
      field = "";
    } else {
      field += char;
    }
  }

  if (quoted) {
    throw new Error("CSV의 따옴표가 닫히지 않았습니다.");
  }

  row.push(field);

  if (row.some(value => value.trim() !== "")) {
    rows.push(row);
  }

  if (rows.length < 2) {
    throw new Error("CSV에 열 제목과 실험 데이터가 필요합니다.");
  }

  const tidy = value =>
    String(value || "").replace(/\s+/g, "").trim();

  /*
   * 기존 정규화 CSV:
   * sample_id, metric, two_pr 등의 열을 그대로 읽습니다.
   */
  if (rows[0].includes("id") && rows[0].includes("twoPr") && rows[0].includes("end_type")) {
    const headers = rows[0];
    return rows.slice(1).map((values, i) => {
      const raw = Object.fromEntries(headers.map((k,j) => [k, values[j] ?? ""]));
      return {sample_id:raw.id, paper:raw.paper, structure:raw.structure,
        metric:finiteNumber(raw.twoPr) === null ? "no_2Pr_label" : "2Pr", two_pr:finiteNumber(raw.twoPr),
        source_sheet:"CSV",source_row:i+2, top:raw.top_electrode,bottom:raw.bottom_electrode,
        hzo_nm:raw.thickness_nm,anneal_c:raw.anneal_temp_C,anneal_s:raw.anneal_time_s,
        voltage_v:raw.meas_V,pulse_s:raw.meas_pw_s,frequency_hz:raw.meas_freq_Hz,
        measurement_method:raw.meas_wave,measurement_state:raw.state,endurance_cycles:raw.endurance,
        endurance_relation:raw.end_type,notes:raw.note,raw_json:JSON.stringify(raw),
        verification:"미승인 · Pr 변환 여부 및 원문 조건 확인 필요"};
    });
  }
  const normalizedHeaderIndex = rows.findIndex(values => {
    const names = values.map(value => String(value).trim());

    return ["sample_id", "metric", "two_pr"]
      .every(name => names.includes(name));
  });

  if (normalizedHeaderIndex >= 0) {
    const headers = rows[normalizedHeaderIndex]
      .map(value => String(value).trim());

    return rows
      .slice(normalizedHeaderIndex + 1)
      .filter(values => values.some(value => value.trim() !== ""))
      .map(values => {
        const record = {};

        headers.forEach((header, index) => {
          record[header] =
            values[index] === undefined ? "" : values[index];
        });

        return record;
      });
  }

  /*
   * HZO 데이터셋 v3:
   * 제목·설명 줄을 건너뛰고 실제 열 제목을 찾습니다.
   */
  const headerIndex = rows.findIndex(values => {
    const names = values.map(tidy);

    return names.includes("ID") &&
      names.includes("소자구조") &&
      names.includes("학습사용");
  });

  if (headerIndex < 0) {
    throw new Error(
      "실험 데이터 열 제목을 찾지 못했습니다. " +
      "ID·소자구조·학습사용 열이 있는 데이터 시트를 CSV로 저장하세요."
    );
  }

  const headers = rows[headerIndex].map(tidy);

  const exactIndex = name => headers.indexOf(tidy(name));

  const prefixIndex = prefix =>
    headers.findIndex(name => name.startsWith(tidy(prefix)));

  const valueAt = (values, index) =>
    index >= 0 && values[index] !== undefined
      ? String(values[index]).trim()
      : "";

  const get = (values, name) =>
    valueAt(values, exactIndex(name));

  const getPrefix = (values, prefix) =>
    valueAt(values, prefixIndex(prefix));

  /*
   * 첫 번째 측정 블록은 2Pr,
   * 뒤의 반복되는 전압·주파수 열은 Endurance 블록입니다.
   */
  const twoPrIndex = headers.findIndex(name =>
    /^2Pr(?:$|[?μµu(（])/.test(name)
  );

  if (twoPrIndex < 0) {
    throw new Error("2Pr 측정값 열을 찾지 못했습니다.");
  }

  function beforeTwoPrIndex(prefix) {
    return headers.findIndex((name, index) =>
      index < twoPrIndex && name.startsWith(tidy(prefix))
    );
  }

  const voltageIndex = beforeTwoPrIndex("인가전압");
  const frequencyIndex = beforeTwoPrIndex("주파수");
  const pulseIndex = beforeTwoPrIndex("펄스폭");

  const numeric = value => {
    if (value === "" || value === null || value === undefined) {
      return null;
    }

    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  };

  const records = [];

  for (const values of rows.slice(headerIndex + 1)) {
    const id = get(values, "ID");

    if (!id || id === "ID") {
      continue;
    }

    const twoPr = numeric(valueAt(values, twoPrIndex));

    /*
     * 원본의 모든 열을 번호와 함께 보존합니다.
     * 반복되는 열 이름도 덮어쓰지 않습니다.
     */
    const original = values.map((value, index) => ({
      column: index + 1,
      header: headers[index] || "",
      value: value
    }));

    const originalNote = get(values, "비고");
    const recommendation = get(values, "학습사용");

    records.push({
      sample_id: id,
      paper: get(values, "출처키"),
      doi: get(values, "DOI") || get(values, "출처DOI"),
      source_url: get(values, "원문") || get(values, "출처URL"),
      source_locator: get(values, "Fig/Table"),

      metric: twoPr !== null ? "2Pr" : "no_2Pr_label",
      two_pr: twoPr,

      structure: get(values, "소자구조"),

      /*
       * 전극 문자열은 그대로 보존합니다.
       * 예: W 45nm + Pt 50nm를 단일 W 전극으로 바꾸지 않습니다.
       */
      top: get(values, "상부전극"),
      bottom: get(values, "하부전극"),

      hzo_nm: numeric(getPrefix(values, "HZO두께")),

      /*
       * 전극 전체 두께와 삽입층 두께는 문자열에서 추측하지 않습니다.
       */
      top_nm: null,
      bottom_nm: null,
      top_interlayer_nm: null,
      bottom_interlayer_nm: null,

      /*
       * RTA라는 열 이름만으로 각 행의 열처리 방식을
       * 검증 완료로 판단하지 않습니다.
       */
      anneal_type: null,
      anneal_c: numeric(getPrefix(values, "RTA온도")),
      anneal_s: numeric(getPrefix(values, "RTA시간")),
      atmosphere: get(values, "분위기"),

      voltage_v: numeric(valueAt(values, voltageIndex)),
      frequency_hz: numeric(valueAt(values, frequencyIndex)),
      pulse_s: numeric(valueAt(values, pulseIndex)),

      measurement_state: get(values, "측정상태"),
      measurement_method: "",
      wake_cycles: null,

      deposition: get(values, "증착법"),
      ald_c: numeric(getPrefix(values, "증착온도")),

      verification: "v3 가져오기 · 미승인 · 원문 검토 필요",

      notes:
        "원본 학습사용 표기: " + recommendation + "\n" +
        "원본 비고: " + originalNote + "\n" +
        "주의: 이 파일은 Pr를 두 배로 변환한 값을 포함할 수 있습니다. " +
        "원문 측정 정의를 확인하기 전에는 학습에 사용하지 마세요.\n" +
        "원본 전체 열: " + JSON.stringify(original)
    });
  }

  if (!records.length) {
    throw new Error(
      "열 제목은 찾았지만 실험 데이터 행을 찾지 못했습니다."
    );
  }

  return records;
}

async function importFile() {
  const file = byId("dataFile").files[0];

      if (!file) {
        byId("importStatus").textContent = "먼저 파일을 선택하세요.";
        return;
      }

      if (file.size > 5 * 1024 * 1024) {
        byId("importStatus").textContent = "5 MB 이하 파일을 사용하세요.";
        return;
      }

      try {
        const text = await file.text();
        let records;

        if (file.name.toLowerCase().endsWith(".json")) {
          records = JSON.parse(text);

          if (!Array.isArray(records)) {
            throw new Error("JSON 최상위 값은 기록 배열이어야 합니다.");
          }

          for (const row of records) {
            if (
              !row ||
              typeof row !== "object" ||
              !Object.prototype.hasOwnProperty.call(row, "sample_id") ||
              !Object.prototype.hasOwnProperty.call(row, "metric") ||
              !Object.prototype.hasOwnProperty.call(row, "two_pr")
            ) {
              throw new Error(
                "각 JSON 기록에 sample_id, metric, two_pr가 필요합니다."
              );
            }
          }
        } else if (file.name.toLowerCase().endsWith(".csv")) {
          records = parseCSV(text);
        } else {
          throw new Error("CSV 또는 JSON 파일만 지원합니다.");
        }

        if (!records.length) {
          throw new Error("추가할 기록이 없습니다.");
        }

        if (records.length > 2000) {
          throw new Error("한 번에 2,000행 이하로 추가하세요.");
        }

        const incoming = records.map((row, index) => {
          return normalizeRecord(row, file.name, index, true);
        });

        const known = new Set(localData.map((row) => JSON.stringify(row)));

        let added = 0;
        const next = localData.slice();

        incoming.forEach((row) => {
          const signature = JSON.stringify(row);

          if (!known.has(signature)) {
            next.push(row);
            known.add(signature);
            added++;
          }
        });

        if (next.length > 5000) {
          throw new Error(
            "브라우저 임시 저장은 5,000행까지 지원합니다. " +
            "기존 자료를 다운로드한 뒤 정리하세요."
          );
        }

        /*
         * 저장이 성공한 경우에만 화면 데이터에 반영합니다.
         */
        localStorage.setItem(DATA_KEY, JSON.stringify(next));
        localData = next;

        rebuildFilterOptions();
        resetFilters();

        byId("importStatus").textContent =
          added + "행을 이 브라우저의 미승인 후보로 추가했습니다. " +
          "동일한 임시 기록은 중복 추가하지 않았습니다. " +
          "GitHub나 모델에는 반영되지 않았습니다.";
      } catch (error) {
        byId("importStatus").textContent =
          "불러오기 실패: " + error.message;
      }
    }

    function downloadJSON(value, filename) {
      const blob = new Blob(
        [JSON.stringify(value, null, 2)],
        { type: "application/json;charset=utf-8" }
      );

      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");

      link.href = url;
      link.download = filename;

      document.body.append(link);
      link.click();
      link.remove();

      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    function getNotes() {
      return {
        reference: byId("paperReference").value.trim(),
        text: byId("researchNotes").value.trim(),
        verification: "미승인 · 원문 검토 필요",
        saved_at: new Date().toISOString()
      };
    }

    function restoreNotes() {
      try {
        const notes = JSON.parse(
          localStorage.getItem(NOTES_KEY) || "null"
        );

        if (notes) {
          byId("paperReference").value = notes.reference || "";
          byId("researchNotes").value = notes.text || "";
        }
      } catch {
        byId("notesStatus").textContent =
          "기존 메모를 읽지 못했습니다.";
      }
    }

    byId("findExperiments").addEventListener("click", findExperiments);

    byId("processForm").addEventListener("submit", (event) => {
      event.preventDefault();
      findExperiments();
    });

    byId("searchInput").addEventListener("input", () => {
      visibleLimit = 25;
      render();
    });

    ["sourceFilter", "annealFilter", "onlyTwoPr", "structureFilter", "metricFilter"].forEach((id) => {
      byId(id).addEventListener("change", () => {
        visibleLimit = 25;
        render();
      });
    });

    byId("resetFilters").addEventListener("click", resetFilters);

    byId("showMore").addEventListener("click", () => {
      visibleLimit += 50;
      render();
    });

    byId("thicknessAxis").addEventListener("click", () => {
      chartAxis = "hzo_nm";

      byId("thicknessAxis").classList.add("active");
      byId("temperatureAxis").classList.remove("active");

      byId("thicknessAxis").setAttribute("aria-pressed", "true");
      byId("temperatureAxis").setAttribute("aria-pressed", "false");

      render();
    });

    byId("temperatureAxis").addEventListener("click", () => {
      chartAxis = "anneal_c";

      byId("temperatureAxis").classList.add("active");
      byId("thicknessAxis").classList.remove("active");

      byId("temperatureAxis").setAttribute("aria-pressed", "true");
      byId("thicknessAxis").setAttribute("aria-pressed", "false");

      render();
    });

    byId("importFile").addEventListener("click", importFile);

    byId("saveNotes").addEventListener("click", () => {
      try {
        localStorage.setItem(NOTES_KEY, JSON.stringify(getNotes()));

        byId("notesStatus").textContent =
          "이 브라우저에 저장했습니다. 사이트 전체에는 반영되지 않습니다.";
      } catch {
        byId("notesStatus").textContent =
          "브라우저 저장이 불가능합니다. 메모 다운로드를 이용하세요.";
      }
    });

    byId("downloadNotes").addEventListener("click", () => {
      downloadJSON(getNotes(), "hzo_research_notes.json");
    });

    byId("downloadLocalData").addEventListener("click", () => {
      downloadJSON(localData, "hzo_unapproved_candidates.json");
    });

    byId("clearLocalData").addEventListener("click", () => {
      if (!confirm(
        "이 브라우저에 추가한 후보 데이터를 삭제할까요? " +
        "기존 사이트 원본 데이터는 삭제되지 않습니다."
      )) {
        return;
      }

      try {
        localStorage.removeItem(DATA_KEY);
        localData = [];

        rebuildFilterOptions();
        resetFilters();

        byId("importStatus").textContent =
          "브라우저에 추가한 후보 데이터만 삭제했습니다.";
      } catch {
        byId("importStatus").textContent =
          "브라우저 저장소에 접근할 수 없어 삭제하지 못했습니다.";
      }
    });

    async function loadBaseData() {
      try {
        const response = await fetch("data.json", {
          cache: "no-cache"
        });

        if (!response.ok) {
          throw new Error("data.json 응답: HTTP " + response.status);
        }

        const payload = await response.json();

        if (!Array.isArray(payload)) {
          throw new Error("data.json이 기록 배열 형식이 아닙니다.");
        }

        baseData = payload.map((row, index) => {
          return normalizeRecord(row, "기존 문헌 자료", index, false);
        });

        dataLoadFinished = true;

        rebuildFilterOptions();
        render();

        byId("loadStatus").textContent =
          "기존 자료 " + baseData.length + "행을 불러왔습니다. " +
          "수치 확인은 학습 승인과 다릅니다. " +
          "초록색 버튼은 입력 조건을 확인하고 관련 실험값을 검색합니다.";
      } catch (error) {
        dataLoadFinished = true;

        rebuildFilterOptions();
        render();

        byId("loadStatus").classList.add("warning");

        byId("loadStatus").textContent =
          "기존 데이터를 불러오지 못했습니다. " +
          error.message +
          ". GitHub 저장소의 docs/data.json 파일과 배포 상태를 확인하세요. " +
          "자료 추가란의 브라우저 임시 기능은 별도로 사용할 수 있습니다.";
      }
    }

    restoreLocalData();
    restoreNotes();
    rebuildFilterOptions();
    render();
    loadBaseData();

    function selectStructure() {
      const mfis = byId("deviceStructure").value === "MFIS";
      byId("mfisFields").hidden = !mfis;
      byId("structureTag").textContent = mfis ? "MFIS" : "MFM";
      byId("resultTarget").textContent = mfis ? "Memory Window / ΔVth" : "2Pr";
      byId("resultUnit").textContent = mfis ? "V" : "μC/cm²";
      byId("deviceStack").textContent = mfis ? "Metal gate / HZO / Insulator / Semiconductor" : "Metal / HZO / Metal";
      byId("predictButton").textContent = (mfis ? "Memory Window / 문턱전압" : "2Pr") + " 예측 · 검증 모델 없음";
      byId("predictionStatus").textContent = mfis ? "MFIS 독립 모델 없음 · Memory Window/문턱전압 수치 레이블 없음 · 2Pr/Endurance도 미검증 · 예측/추천 차단" : "MFM: 승인 0행 · Random Forest 학습 차단 · 열화 곡선/Endurance/추천 미검증";
      selectedElectrodes = null;
      byId("structureFilter").value = byId("deviceStructure").value;
      byId("conditionMessage").hidden = true;
      render();
    }
    byId("deviceStructure").addEventListener("change", selectStructure);
    byId("downloadResults").addEventListener("click", () => {
      const rows=getFilteredRows();
      const cols=["record_id","sample_id","structure","metric","two_pr","pr","two_pr_lower_bound","endurance_cycles","endurance_relation","doi","source_file","possible_overlap","source_sheet","source_row","source_locator","measurement_state","voltage_definition"];
      const cell = v => '"' + String(v ?? "").replaceAll('"','""') + '"';
      const csv = [cols,...rows.map(r => cols.map(k => r[k]))].map(r => r.map(cell).join(",")).join("\r\n");
      const a=document.createElement("a"); const url=URL.createObjectURL(new Blob(["\ufeff",csv],{type:"text/csv;charset=utf-8"}));
      a.href=url;a.download="hzo_filtered_measurements.csv";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    });
    fetch("quality.json").then(r=>{if(!r.ok)throw new Error(r.status);return r.json();}).then(q=>{
      byId("subsetCount").textContent = q.duplicate_subset_rows + (q.v2_subset_rows_not_added || 0);
      const note=document.createElement("p");note.className="caption";
      note.textContent="원본 출처 기록 " + q.total_records + "행 · 출처 간 중복 검토 후보 " + q.possible_cross_source_overlap_rows + "행. 독립 실험 수가 아닙니다. 반복 조건은 보존하며 분류 시트는 합산하지 않았습니다.";
      byId("loadStatus").after(note);
    }).catch(()=>{byId("subsetCount").textContent="—";});
