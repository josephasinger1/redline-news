(function () {
  "use strict";

  var feedEl = document.getElementById("feed");
  var stateEl = document.getElementById("state");
  var chipsEl = document.getElementById("chips");
  var updatedEl = document.getElementById("updated");
  var searchEl = document.getElementById("search");

  var articles = [];
  var activeBrand = "All";
  var query = "";

  function timeAgo(iso) {
    var s = (Date.now() - new Date(iso).getTime()) / 1000;
    if (s < 90) return "just now";
    if (s < 3600) return Math.round(s / 60) + "m ago";
    if (s < 86400) return Math.round(s / 3600) + "h ago";
    return Math.round(s / 86400) + "d ago";
  }

  function dayLabel(iso) {
    var d = new Date(iso);
    var today = new Date();
    var yest = new Date(today.getTime() - 86400000);
    var same = function (a, b) {
      return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
    };
    if (same(d, today)) return "Today";
    if (same(d, yest)) return "Yesterday";
    return d.toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" });
  }

  function esc(s) {
    var div = document.createElement("div");
    div.textContent = s || "";
    return div.innerHTML;
  }

  function brandCounts() {
    var counts = {};
    articles.forEach(function (a) {
      (a.brands || []).forEach(function (b) {
        counts[b] = (counts[b] || 0) + 1;
      });
    });
    return counts;
  }

  function renderChips() {
    var counts = brandCounts();
    var names = Object.keys(counts).sort(function (a, b) {
      if (a === "General") return 1;
      if (b === "General") return -1;
      return counts[b] - counts[a];
    });
    var htmlStr = chipHtml("All", articles.length);
    names.forEach(function (n) {
      htmlStr += chipHtml(n, counts[n]);
    });
    chipsEl.innerHTML = htmlStr;
    chipsEl.querySelectorAll(".chip").forEach(function (el) {
      el.addEventListener("click", function () {
        activeBrand = el.getAttribute("data-brand");
        renderChips();
        renderFeed();
      });
    });
  }

  function chipHtml(name, count) {
    var cls = "chip" + (name === activeBrand ? " active" : "");
    return (
      '<button class="' + cls + '" data-brand="' + esc(name) + '">' +
      esc(name) + '<span class="n">' + count + "</span></button>"
    );
  }

  function matches(a) {
    if (activeBrand !== "All" && (a.brands || []).indexOf(activeBrand) === -1) return false;
    if (query) {
      var hay = (a.title + " " + a.summary + " " + a.source + " " + (a.brands || []).join(" ")).toLowerCase();
      return hay.indexOf(query) !== -1;
    }
    return true;
  }

  function renderFeed() {
    var visible = articles.filter(matches);
    if (!visible.length) {
      feedEl.innerHTML =
        '<div class="state">' +
        (articles.length
          ? "Nothing matches that filter — try another brand or search."
          : "No stories yet. The first daily scrape hasn’t landed — check back soon!") +
        "</div>";
      return;
    }
    var htmlStr = "";
    var lastDay = null;
    visible.forEach(function (a) {
      var day = dayLabel(a.published);
      if (day !== lastDay) {
        htmlStr += '<h3 class="dayhead">' + esc(day) + "</h3>";
        lastDay = day;
      }
      htmlStr += cardHtml(a);
    });
    feedEl.innerHTML = htmlStr;
  }

  function cardHtml(a) {
    var img = a.image
      ? '<img src="' + esc(a.image) + '" alt="" loading="lazy" onerror="this.remove()">'
      : "";
    var tags = (a.brands || [])
      .map(function (b) {
        return '<span class="tag">' + esc(b) + "</span>";
      })
      .join("");
    return (
      '<a class="card" href="' + esc(a.url) + '" target="_blank" rel="noopener">' +
      img +
      '<div class="card-body">' +
      '<div class="meta"><span class="src">' + esc(a.source) + "</span><span>·</span><span>" +
      timeAgo(a.published) + "</span></div>" +
      "<h2>" + esc(a.title) + "</h2>" +
      (a.summary ? "<p>" + esc(a.summary) + "</p>" : "") +
      '<div class="tags">' + tags + "</div>" +
      "</div></a>"
    );
  }

  searchEl.addEventListener("input", function () {
    query = searchEl.value.trim().toLowerCase();
    renderFeed();
  });

  fetch("data/news.json", { cache: "no-store" })
    .then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then(function (data) {
      articles = data.articles || [];
      if (data.generated_at) {
        updatedEl.textContent = "Updated " + timeAgo(data.generated_at);
      }
      renderChips();
      renderFeed();
    })
    .catch(function (err) {
      stateEl.textContent = "Couldn’t load the feed (" + err.message + "). Pull to refresh or try again later.";
    });
})();
