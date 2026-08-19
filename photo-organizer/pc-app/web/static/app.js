// ビルド不要のシンプルなVanilla JS。fetch APIでバックエンドと通信する。

async function postForm(url, data) {
  const body = new URLSearchParams(data);
  const res = await fetch(url, { method: "POST", body });
  if (!res.ok) {
    const detail = await res.text();
    alert("エラーが発生しました: " + detail);
    throw new Error(detail);
  }
  return res.json();
}

function startScan() {
  const folder = document.getElementById("root-folder").value.trim();
  if (!folder) {
    alert("フォルダのパスを入力してください");
    return;
  }
  postForm("/api/scan", { root_folder: folder }).then(() => {
    pollJobStatus();
  }).catch(() => {});
}

function pollJobStatus() {
  const statusEl = document.getElementById("job-status");
  if (!statusEl) return;
  const timer = setInterval(async () => {
    const res = await fetch("/api/job-status");
    const data = await res.json();
    if (data.job) {
      statusEl.textContent = `解析中... ${data.job.processed_files}/${data.job.total_files || "?"}件処理済み`;
    }
    if (!data.running) {
      clearInterval(timer);
      statusEl.textContent = "解析が完了しました。ページを再読み込みします。";
      setTimeout(() => window.location.reload(), 1000);
    }
  }, 2000);
}

function setSimilarityDecision(groupId, mediaId, decision) {
  postForm(`/api/similarity-groups/${groupId}/items/${mediaId}/decision`, { decision }).then(() => {
    window.location.reload();
  });
}

function setCandidateStatus(mediaId, status) {
  postForm(`/api/delete-candidates/${mediaId}/status`, { user_status: status }).then(() => {
    window.location.reload();
  });
}

async function generateManifest() {
  if (!confirm("削除候補を確定し、delete_manifest.jsonを生成します。よろしいですか?")) return;
  const res = await fetch("/api/generate-manifest", { method: "POST" });
  const data = await res.json();
  alert(`manifestを生成しました(${data.item_count}件)。\n保存先: ${data.file}\nこのファイルをUSB/SSD経由でiPhoneアプリへ連携してください。`);
  window.location.reload();
}

function updateThreshold(key) {
  const input = document.getElementById("threshold-" + key);
  postForm("/api/settings/threshold", { key, value: input.value }).then(() => {
    alert("設定を保存しました。次回の「解析開始」から反映されます。");
  });
}
