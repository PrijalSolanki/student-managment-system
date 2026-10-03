/* SMS - progressive enhancement helpers (Bootstrap 5 based). */
(function () {
  "use strict";

  function ready(fn) {
    if (document.readyState !== "loading") {
      fn();
    } else {
      document.addEventListener("DOMContentLoaded", fn);
    }
  }

  /* ---------------------------------------------------------------- sidebar */
  ready(function () {
    var sidebar = document.getElementById("smsSidebar");
    document.querySelectorAll("[data-sidebar-toggle]").forEach(function (button) {
      button.addEventListener("click", function () {
        if (sidebar) {
          sidebar.classList.toggle("is-open");
        }
      });
    });
  });

  /* --------------------------------------------------- confirm before POST */
  ready(function () {
    document.querySelectorAll("form[data-confirm]").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        if (!window.confirm(form.dataset.confirm)) {
          event.preventDefault();
        }
      });
    });
  });

  /* ------------------------------------------------------- filters autosubmit */
  ready(function () {
    document.querySelectorAll("[data-filter-form]").forEach(function (form) {
      form.querySelectorAll("select, input[type=date]").forEach(function (control) {
        control.addEventListener("change", function () {
          form.submit();
        });
      });
    });
  });

  /* -------------------------------------------------------- bulk selections */
  ready(function () {
    document.querySelectorAll("[data-select-all]").forEach(function (master) {
      master.addEventListener("change", function () {
        var name = master.dataset.selectAll;
        document
          .querySelectorAll('input[type=checkbox][name="' + name + '"]')
          .forEach(function (box) {
            box.checked = master.checked;
          });
        document.querySelectorAll("[data-bulk-target]").forEach(function (el) {
          el.classList.toggle("d-none", !master.checked);
        });
      });
    });
  });

  /* ---------------------------------------------------------- attendance UI */
  ready(function () {
    var grid = document.querySelector("[data-attendance-grid]");
    if (!grid) {
      return;
    }
    var counter = document.querySelector("[data-attendance-summary]");
    function recount() {
      if (!counter) {
        return;
      }
      var stats = { PRESENT: 0, ABSENT: 0, LEAVE: 0 };
      grid.querySelectorAll("select[name^='status_']").forEach(function (select) {
        stats[select.value] = (stats[select.value] || 0) + 1;
      });
      counter.textContent =
        "Present " + (stats.PRESENT || 0) + " \u00b7 Absent " + (stats.ABSENT || 0) +
        " \u00b7 On leave " + (stats.LEAVE || 0);
    }
    grid.addEventListener("change", function (event) {
      if (event.target.name && event.target.name.indexOf("status_") === 0) {
        var row = event.target.closest("tr");
        if (row) {
          row.classList.toggle("table-warning", event.target.value === "ABSENT");
        }
        recount();
      }
    });
    var setAll = function (status) {
      grid.querySelectorAll("select[name^='status_']").forEach(function (select) {
        select.value = status;
        var row = select.closest("tr");
        if (row) {
          row.classList.toggle("table-warning", status === "ABSENT");
        }
      });
      recount();
    };
    document.querySelectorAll("[data-mark-all]").forEach(function (button) {
      button.addEventListener("click", function () {
        setAll(button.dataset.markAll);
      });
    });
    recount();
  });

  /* --------------------------------------------------------------- mark entry */
  ready(function () {
    var grid = document.querySelector("[data-marks-grid]");
    if (!grid) {
      return;
    }
    var summary = document.querySelector("[data-marks-summary]");
    var recalc = function () {
      var entered = 0;
      var total = 0;
      grid.querySelectorAll("input[name^='marks_']").forEach(function (input) {
        var max = parseFloat(input.dataset.max || "0");
        var value = parseFloat(input.value || "0");
        total += max;
        if (input.value !== "" && !isNaN(value)) {
          entered += 1;
        }
        input.classList.toggle("is-invalid", value > max && input.value !== "");
      });
      if (summary) {
        summary.textContent = entered + " of " + grid.querySelectorAll("input[name^='marks_']").length +
          " entries saved (" + Math.round(total) + " total marks available)";
      }
    };
    grid.addEventListener("input", recalc);
    recalc();
  });

  /* ----------------------------------------------------------------- charts */
  window.smsChart = function (canvasId, config) {
    var canvas = document.getElementById(canvasId);
    if (!canvas || typeof Chart === "undefined") {
      return null;
    }
    var context = canvas.getContext("2d");
    return new Chart(context, config);
  };

  /* --------------------------------------------------- dependent ajax fields */
  ready(function () {
    var courseSelect = document.getElementById("id_course");
    var semesterSelect = document.getElementById("id_semester");
    var departmentSelect = document.getElementById("id_department");
    if (!courseSelect || !semesterSelect) {
      return;
    }
    var syncDepartment = function () {
      if (!departmentSelect) {
        return;
      }
      var option = courseSelect.options[courseSelect.selectedIndex];
      var value = option ? option.dataset.department : "";
      departmentSelect.value = value || "";
    };
    courseSelect.addEventListener("change", syncDepartment);
    syncDepartment();
  });

  /* ------------------------------------------------------------ auto dismiss */
  ready(function () {
    document.querySelectorAll(".alert[data-autodismiss]").forEach(function (alert) {
      window.setTimeout(function () {
        if (window.bootstrap && window.bootstrap.Alert) {
          window.bootstrap.Alert.getOrCreateInstance(alert).close();
        }
      }, 6000);
    });
  });
})();