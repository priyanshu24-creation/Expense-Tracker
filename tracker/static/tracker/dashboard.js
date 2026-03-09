(function () {
  window.dashboardBoot = true;
  const qs = (sel) => document.querySelector(sel);
  const qsa = (sel) => Array.from(document.querySelectorAll(sel));

  const getJSON = (id) => {
    const el = document.getElementById(id);
    if (!el) return null;
    try {
      return JSON.parse(el.textContent);
    } catch (err) {
      return null;
    }
  };

  const openModal = (modal) => {
    if (modal) modal.classList.add("open");
  };
  const closeModal = (modal) => {
    if (modal) modal.classList.remove("open");
  };

  document.addEventListener("click", (event) => {
    const closeBtn = event.target.closest("[data-modal-close]");
    if (closeBtn) {
      const modal = closeBtn.closest(".modal");
      closeModal(modal);
    }
  });

  qsa(".modal").forEach((modal) => {
    modal.addEventListener("click", (event) => {
      if (event.target === modal) {
        closeModal(modal);
      }
    });
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      qsa(".modal.open").forEach((modal) => closeModal(modal));
      toggleDrawer(false);
    }
  });

  // Profile drawer
  function toggleDrawer(open) {
    const drawer = qs("#profileDrawer");
    const scrim = qs("#drawerScrim");
    if (!drawer || !scrim) return;
    if (open) {
      drawer.classList.add("open");
      scrim.classList.add("open");
    } else {
      drawer.classList.remove("open");
      scrim.classList.remove("open");
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    const openBtn = qs("#openDrawerBtn");
    const closeBtn = qs("#drawerClose");
    const scrim = qs("#drawerScrim");

    if (openBtn) {
      openBtn.addEventListener("click", () => toggleDrawer(true));
      openBtn.addEventListener("touchstart", (e) => {
        e.preventDefault();
        toggleDrawer(true);
      }, { passive: false });
    }
    if (closeBtn) {
      closeBtn.addEventListener("click", () => toggleDrawer(false));
    }
    if (scrim) {
      scrim.addEventListener("click", () => toggleDrawer(false));
      scrim.addEventListener("touchstart", (e) => {
        e.preventDefault();
        toggleDrawer(false);
      }, { passive: false });
    }

    const meterFills = qsa(".meter-fill");
    if (meterFills.length) {
      const values = meterFills.map((el) => parseFloat(el.dataset.value || "0"));
      const totalAbs = values.reduce((sum, value) => sum + Math.abs(value), 0);
      meterFills.forEach((el, index) => {
        const value = values[index];
        if (value < 0) {
          el.classList.add("negative");
        }
        const width = totalAbs ? (Math.abs(value) / totalAbs) * 100 : 0;
        el.style.width = `${width.toFixed(1)}%`;
        const percentLabel = el.closest(".meter-card")?.querySelector(".meter-percent");
        if (percentLabel) {
          percentLabel.textContent = `${totalAbs ? (Math.abs(value) / totalAbs * 100).toFixed(0) : 0}%`;
        }
      });
    }

    // Charts
    const categoryChartData = getJSON("category-chart-data");
    const trendChartData = getJSON("trend-chart-data");
    const incomeExpenseChartData = getJSON("income-expense-chart-data");

    const chartLib = window.Chart;
    const dataLabelsPlugin = window.ChartDataLabels || null;

    if (chartLib && categoryChartData && qs("#categoryChart")) {
      const categoryCanvas = qs("#categoryChart");
      if (categoryCanvas.dataset.chartReady === "1") {
        // chart already rendered
      } else {
      const pieOptions = {
        plugins: {
          legend: { position: "bottom" },
        },
      };
      if (dataLabelsPlugin) {
        pieOptions.plugins.datalabels = {
          color: () => document.body.classList.contains("theme-dark") ? "#e2e8f0" : "#0f172a",
          formatter: (value, ctx) => {
            const total = ctx.chart.data.datasets[0].data.reduce((a, b) => a + b, 0);
            if (!total) return "";
            const percent = (value / total) * 100;
            return `${percent.toFixed(0)}%`;
          },
        };
      }
        new chartLib(categoryCanvas, {
        type: "pie",
        data: {
          labels: categoryChartData.labels,
          datasets: [{
            data: categoryChartData.values,
            backgroundColor: [
              "#6366f1",
              "#10b981",
              "#f59e0b",
              "#ef4444",
              "#0ea5e9",
              "#8b5cf6",
            ],
          }],
        },
        options: pieOptions,
        plugins: dataLabelsPlugin ? [dataLabelsPlugin] : [],
        });
        categoryCanvas.dataset.chartReady = "1";
      }
    }

    if (chartLib && trendChartData && qs("#trendChart")) {
      const trendCanvas = qs("#trendChart");
      if (trendCanvas.dataset.chartReady === "1") {
        // chart already rendered
      } else {
        new chartLib(trendCanvas, {
        type: "line",
        data: {
          labels: trendChartData.labels,
          datasets: [{
            label: "Expenses",
            data: trendChartData.values,
            borderColor: "#4f46e5",
            backgroundColor: "rgba(79,70,229,.2)",
            fill: true,
            tension: 0.4,
          }],
        },
        options: {
          plugins: { legend: { display: false } },
          scales: {
            y: { beginAtZero: true },
          },
        },
        });
        trendCanvas.dataset.chartReady = "1";
      }
    }

    if (chartLib && incomeExpenseChartData && qs("#incomeExpenseChart")) {
      const incomeExpenseCanvas = qs("#incomeExpenseChart");
      if (incomeExpenseCanvas.dataset.chartReady === "1") {
        // chart already rendered
      } else {
        new chartLib(incomeExpenseCanvas, {
        type: "bar",
        data: {
          labels: incomeExpenseChartData.labels,
          datasets: [{
            data: incomeExpenseChartData.values,
            backgroundColor: ["#10b981", "#ef4444"],
            borderRadius: 8,
          }],
        },
        options: {
          plugins: { legend: { display: false } },
          scales: {
            y: { beginAtZero: true },
          },
        },
        });
        incomeExpenseCanvas.dataset.chartReady = "1";
      }
    }

    // Delete transaction modal
    const deleteModal = qs("#deleteModal");
    const deleteForm = qs("#deleteForm");
    const deleteText = qs("#deleteModalText");
    qsa("[data-delete-url]").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (deleteForm) {
          deleteForm.action = btn.dataset.deleteUrl;
        }
        if (deleteText) {
          deleteText.textContent = `Delete ${btn.dataset.deleteLabel}?`;
        }
        openModal(deleteModal);
      });
    });

    // Reset transactions modal
    const resetModal = qs("#resetTransactionsModal");
    qsa("[data-reset-transactions]").forEach((btn) => {
      btn.addEventListener("click", () => {
        openModal(resetModal);
      });
    });

    // Edit transaction modal
    const editModal = qs("#editModal");
    const editForm = qs("#editForm");
    qsa("[data-edit-transaction]").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (editForm && btn.dataset.editUrl) {
          editForm.action = btn.dataset.editUrl;
        }
        qs("#editType").value = btn.dataset.type || "expense";
        qs("#editPayment").value = btn.dataset.payment || "online";
        qs("#editAmount").value = btn.dataset.amount || "";
        qs("#editCategory").value = btn.dataset.category || "other";
        qs("#editDate").value = btn.dataset.date || "";
        qs("#editDescription").value = btn.dataset.description || "";
        openModal(editModal);
      });
    });

    // Recurring edit modal
    const recurringEditModal = qs("#recurringEditModal");
    const recurringEditForm = qs("#recurringEditForm");
    qsa("[data-edit-recurring]").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (recurringEditForm && btn.dataset.editUrl) {
          recurringEditForm.action = btn.dataset.editUrl;
        }
        qs("#recurringType").value = btn.dataset.type || "expense";
        qs("#recurringPayment").value = btn.dataset.payment || "online";
        qs("#recurringAmount").value = btn.dataset.amount || "";
        qs("#recurringCategory").value = btn.dataset.category || "other";
        qs("#recurringRepeat").value = btn.dataset.repeat || "monthly";
        qs("#recurringStart").value = btn.dataset.start || "";
        qs("#recurringEnd").value = btn.dataset.end || "";
        qs("#recurringDescription").value = btn.dataset.description || "";
        const weekdayInputs = qsa("#recurringEditForm input[name='weekdays']");
        weekdayInputs.forEach((input) => {
          input.checked = false;
        });
        const days = (btn.dataset.weekdays || "").split(",").filter(Boolean);
        if (days.length) {
          weekdayInputs.forEach((input) => {
            if (days.includes(input.value)) {
              input.checked = true;
            }
          });
        }
        openModal(recurringEditModal);
      });
    });

    // Recurring delete modal
    const recurringDeleteModal = qs("#recurringDeleteModal");
    const recurringDeleteForm = qs("#recurringDeleteForm");
    qsa("[data-delete-recurring-url]").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (recurringDeleteForm) {
          recurringDeleteForm.action = btn.dataset.deleteRecurringUrl;
        }
        openModal(recurringDeleteModal);
      });
    });

    // Smart categorization
    const keywordMap = getJSON("keyword-map-data") || {};
    const findCategory = (text) => {
      const value = (text || "").toLowerCase();
      if (!value) return null;
      for (const [category, keywords] of Object.entries(keywordMap)) {
        if (keywords.some((keyword) => value.includes(keyword))) {
          return category;
        }
      }
      return null;
    };

    const attachSuggestion = (inputId, selectId, hintId) => {
      const input = qs(inputId);
      const select = qs(selectId);
      const hint = hintId ? qs(hintId) : null;
      if (!input || !select) return;
      input.addEventListener("input", () => {
        if (select.value !== "auto") return;
        const suggestion = findCategory(input.value);
        if (suggestion) {
          select.value = suggestion;
          if (hint) hint.textContent = `Suggested category: ${suggestion}`;
        } else if (hint) {
          hint.textContent = "";
        }
      });
    };

    attachSuggestion("#descriptionInput", "#categorySelect", "#categoryHint");
    attachSuggestion("#editDescription", "#editCategory");

    // Dark mode
    const themeToggle = qs("#themeToggle");
    const storage = (() => {
      try {
        return window.localStorage;
      } catch (err) {
        return null;
      }
    })();
    const applyTheme = (theme) => {
      if (theme === "dark") {
        document.body.classList.add("theme-dark");
        if (themeToggle) themeToggle.textContent = "Light Mode";
      } else {
        document.body.classList.remove("theme-dark");
        if (themeToggle) themeToggle.textContent = "Dark Mode";
      }
    };
    const storedTheme = (storage && storage.getItem("theme")) || "light";
    applyTheme(storedTheme);
    if (themeToggle) {
      themeToggle.addEventListener("click", () => {
        const newTheme = document.body.classList.contains("theme-dark") ? "light" : "dark";
        if (storage) {
          storage.setItem("theme", newTheme);
        }
        applyTheme(newTheme);
      });
    }

    // PWA install
    let deferredInstallPrompt = null;
    const installBtn = qs("#installPwaBtn");
    window.addEventListener("beforeinstallprompt", (e) => {
      e.preventDefault();
      deferredInstallPrompt = e;
      if (installBtn) {
        installBtn.hidden = false;
      }
    });

    window.addEventListener("appinstalled", () => {
      deferredInstallPrompt = null;
      if (installBtn) {
        installBtn.hidden = true;
      }
    });

    if (installBtn) {
      installBtn.addEventListener("click", async () => {
        if (!deferredInstallPrompt) return;
        deferredInstallPrompt.prompt();
        await deferredInstallPrompt.userChoice;
        deferredInstallPrompt = null;
        installBtn.hidden = true;
      });
    }

    window.dashboardReady = true;
  });

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/service-worker.js").catch(() => {});
    });
  }
})();
