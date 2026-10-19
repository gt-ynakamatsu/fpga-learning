/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   FPGAお勉強アプリ — メインアプリ (app.js)
   外部ライブラリ不使用・同梱のみ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */

'use strict';

// ── ユーティリティ ────────────────────────────

const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];
const h = (tag, attrs = {}, ...children) => {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') el.className = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v);
  }
  for (const c of children) {
    if (c == null) continue;
    el.append(typeof c === 'string' ? document.createTextNode(c) : c);
  }
  return el;
};

function showToast(msg, type = 'info', duration = 3500) {
  const container = $('#toast-container');
  const toast = h('div', { class: `toast ${type}` }, msg);
  container.append(toast);
  setTimeout(() => toast.remove(), duration);
}

async function apiFetch(path, opts = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

// ── ルーター ─────────────────────────────────

const routes = {};
function route(pattern, handler) { routes[pattern] = handler; }

function navigate(hash) {
  history.pushState(null, '', hash || '#home');
  renderRoute(hash || '#home');
}

async function renderRoute(hash) {
  const root = $('#app-root');

  // ナビのアクティブ更新
  $$('.nav-link').forEach(a => a.classList.remove('active'));
  if (hash === '#home' || hash === '') $('#nav-home')?.classList.add('active');
  if (hash === '#progress') $('#nav-progress')?.classList.add('active');

  const parts = hash.replace(/^#\/?/, '').split('/');
  const key = parts[0] || 'home';

  root.innerHTML = '<div class="loading-screen"><div class="spinner"></div><p>読み込み中...</p></div>';

  try {
    const handler = routes[key];
    if (handler) {
      await handler(parts, root);
    } else {
      root.innerHTML = '<p>ページが見つかりません。</p>';
    }
  } catch (err) {
    root.innerHTML = `<div class="loading-screen"><p style="color:var(--danger)">エラー: ${escHtml(err.message)}</p></div>`;
  }
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

window.addEventListener('popstate', () => renderRoute(location.hash));
document.addEventListener('click', e => {
  const a = e.target.closest('a[href^="#"]');
  if (a) { e.preventDefault(); navigate(a.getAttribute('href')); }
});

// ── ページ: ホーム ────────────────────────────

route('home', async (_, root) => {
  const [chapters, progressData] = await Promise.all([
    apiFetch('/api/chapters'),
    apiFetch('/api/progress'),
  ]);

  const progressMap = {};
  for (const p of progressData.progress) progressMap[p.lesson_key] = p;

  function chapterProgress(ch) {
    const lessons = ch.lessons || [];
    if (!lessons.length) return 0;
    const done = lessons.filter(lid => {
      const key = `${ch.id}/${lid}`;
      return progressMap[key]?.completed;
    }).length;
    return Math.round((done / lessons.length) * 100);
  }

  root.innerHTML = '';
  root.append(
    h('div', { class: 'home-hero' },
      h('h1', {}, '⚡ FPGAお勉強アプリへようこそ！'),
      h('p', {}, '2進数から始めて、論理回路の基礎を楽しく学ぼう')
    ),
    h('h2', { style: 'font-size:1.1rem;font-weight:700;margin-bottom:1rem;color:var(--gray-500)' }, 'カリキュラム'),
    h('div', { class: 'chapter-grid' },
      ...chapters.map(ch => {
        const pct = chapterProgress(ch);
        const card = h('a', { href: `#chapter/${ch.id}`, class: 'chapter-card' },
          h('div', { class: 'chapter-card-num' }, `第${ch.order}章`),
          h('div', { class: 'chapter-card-title' }, ch.title),
          ch.description ? h('div', { class: 'chapter-card-desc' }, ch.description) : null,
          h('div', { class: 'chapter-progress-bar' },
            h('div', { class: 'chapter-progress-fill', style: `width:${pct}%` })
          )
        );
        return card;
      })
    )
  );
});

// ── ページ: 章 ───────────────────────────────

route('chapter', async ([_, chapterId], root) => {
  const [chapter, lessons, progressData] = await Promise.all([
    apiFetch(`/api/chapters/${chapterId}`),
    apiFetch(`/api/chapters/${chapterId}/lessons`),
    apiFetch('/api/progress'),
  ]);

  const progressMap = {};
  for (const p of progressData.progress) progressMap[p.lesson_key] = p;

  root.innerHTML = '';
  root.append(
    h('a', { href: '#home', class: 'back-link' }, '← ホームへ'),
    h('div', { class: 'chapter-header' },
      h('h1', {}, chapter.title),
      chapter.description ? h('p', {}, chapter.description) : null
    ),
    h('div', { class: 'lesson-list' },
      ...lessons.map((ls, idx) => {
        const prog = progressMap[`${chapterId}/${ls.lesson_id}`];
        const completed = prog?.completed;

        const badges = [];
        if (ls.has_quiz) badges.push(h('span', { class: 'badge-small' }, 'クイズ'));
        if (ls.has_puzzle) badges.push(h('span', { class: 'badge-small puzzle' }, '回路パズル'));
        if (ls.status === 'draft') badges.push(h('span', { class: 'status-draft' }, '下書き'));

        return h('a', { href: `#lesson/${chapterId}/${ls.lesson_id}`, class: `lesson-item ${completed ? 'completed' : ''}` },
          h('div', { class: `lesson-check ${completed ? 'done' : ''}` }, completed ? '✓' : String(idx + 1)),
          h('div', { class: 'lesson-info' },
            h('div', { class: 'lesson-title' }, ls.title),
            ls.estimated_min ? h('div', { class: 'lesson-meta' }, `約${ls.estimated_min}分`) : null
          ),
          badges.length ? h('div', { class: 'lesson-badges' }, ...badges) : null
        );
      })
    )
  );
});

// ── ページ: レッスン ─────────────────────────

route('lesson', async ([_, chapterId, lessonId], root) => {
  const lesson = await apiFetch(`/api/chapters/${chapterId}/lessons/${lessonId}`);

  root.innerHTML = '';

  const statusBadge = lesson.status === 'draft'
    ? h('span', { class: 'status-draft', style: 'margin-left:.5rem' }, '📝 下書き')
    : lesson.status === 'review'
    ? h('span', { class: 'status-review', style: 'margin-left:.5rem' }, '🔍 レビュー中')
    : null;

  root.append(
    h('a', { href: `#chapter/${chapterId}`, class: 'back-link' }, `← 第${chapterId.replace('chapter0','')?.replace('chapter','')}章へ`),
    h('div', { class: 'lesson-header' },
      h('h1', {}, lesson.title, statusBadge)
    ),
    h('div', { class: 'lesson-content', id: 'lesson-content' })
  );
  $('#lesson-content').innerHTML = lesson.content_html || '<p>コンテンツがありません。</p>';

  // クイズセクション
  if (lesson.quiz?.questions?.length) {
    root.append(buildQuizSection(lesson.quiz.questions, chapterId, lessonId));
  }

  // パズルセクション
  if (lesson.puzzle) {
    const puzzleEl = h('div', { id: 'puzzle-mount' });
    root.append(puzzleEl);
    // puzzle.js の PuzzleEditor を初期化
    if (typeof PuzzleEditor !== 'undefined') {
      new PuzzleEditor(puzzleEl, lesson.puzzle, chapterId, lessonId);
    }
  }

  // 前後のレッスンナビ
  const lessons = await apiFetch(`/api/chapters/${chapterId}/lessons`);
  const idx = lessons.findIndex(ls => ls.lesson_id === lessonId);
  const prev = lessons[idx - 1];
  const next = lessons[idx + 1];

  root.append(h('div', { class: 'lesson-nav' },
    prev
      ? h('a', { href: `#lesson/${chapterId}/${prev.lesson_id}`, class: 'btn btn-secondary' }, `← ${prev.title}`)
      : h('a', { href: `#chapter/${chapterId}`, class: 'btn btn-secondary' }, '← レッスン一覧'),
    next
      ? h('a', { href: `#lesson/${chapterId}/${next.lesson_id}`, class: 'btn btn-primary' }, `${next.title} →`)
      : h('a', { href: '#progress', class: 'btn btn-success' }, '🏆 進捗を確認する')
  ));
});

// ── クイズ UI ─────────────────────────────────

function buildQuizSection(questions, chapterId, lessonId) {
  let currentIdx = 0;
  let score = 0;
  const answers = new Array(questions.length).fill(null);

  const section = h('div', { class: 'quiz-section' });

  function render() {
    section.innerHTML = '';
    if (currentIdx >= questions.length) {
      renderResult();
      return;
    }
    const q = questions[currentIdx];
    const letters = ['A', 'B', 'C', 'D', 'E'];

    const progressLabel = h('span', { class: 'quiz-progress' }, `${currentIdx + 1} / ${questions.length}`);
    section.append(
      h('h2', {}, '📝 確認クイズ', progressLabel),
      h('div', { class: 'quiz-question' },
        h('div', { class: 'quiz-question-text' }, `Q${currentIdx + 1}. ${q.question}`),
        h('div', { class: 'quiz-options', id: 'quiz-options' },
          ...q.options.map((opt, i) =>
            h('button', {
              class: 'quiz-option',
              onclick: () => onAnswer(i),
              disabled: answers[currentIdx] !== null ? 'true' : undefined,
            },
              h('span', { class: 'quiz-option-letter' }, letters[i]),
              opt
            )
          )
        ),
        h('div', { class: 'quiz-explanation', id: 'quiz-explanation' },
          `💡 解説: ${q.explanation || ''}`)
      )
    );

    // 既に回答済みなら状態を再現
    if (answers[currentIdx] !== null) {
      applyAnswer(answers[currentIdx], q.answer);
    }

    const navRow = h('div', { class: 'lesson-nav' });
    if (currentIdx > 0) {
      navRow.append(h('button', { class: 'btn btn-secondary', onclick: () => { currentIdx--; render(); } }, '← 前の問題'));
    } else {
      navRow.append(h('span'));
    }
    const nextBtn = h('button', {
      class: 'btn btn-primary',
      id: 'quiz-next-btn',
      onclick: () => { currentIdx++; render(); },
      disabled: answers[currentIdx] === null ? 'true' : undefined,
    }, currentIdx < questions.length - 1 ? '次の問題 →' : '結果を見る');
    navRow.append(nextBtn);
    section.append(navRow);
  }

  async function onAnswer(selectedIdx) {
    if (answers[currentIdx] !== null) return;

    try {
      const q = questions[currentIdx];
      const result = await apiFetch(
        `/api/chapters/${chapterId}/lessons/${lessonId}/quiz/check`,
        { method: 'POST', body: JSON.stringify({ question_id: q.id, answer_index: selectedIdx }) }
      );
      answers[currentIdx] = { selected: selectedIdx, correct: result.correct, correctIdx: result.correct_index };
      if (result.correct) score++;
      applyAnswer(selectedIdx, result.correct_index);
    } catch (e) {
      showToast('回答の送信に失敗しました', 'error');
    }
  }

  function applyAnswer(selectedIdx, correctIdx) {
    const opts = $$('.quiz-option', section);
    opts.forEach((btn, i) => {
      btn.disabled = true;
      if (i === correctIdx) btn.classList.add('correct');
      else if (i === selectedIdx && selectedIdx !== correctIdx) btn.classList.add('wrong');
    });
    const explanation = $('#quiz-explanation', section);
    if (explanation) explanation.classList.add('visible');
    const nextBtn = $('#quiz-next-btn', section);
    if (nextBtn) nextBtn.removeAttribute('disabled');
  }

  async function renderResult() {
    const total = questions.length;
    section.innerHTML = '';
    section.append(
      h('h2', {}, '📝 確認クイズ'),
      h('div', { class: 'quiz-result' },
        h('div', { class: 'quiz-score-big' }, `${score} / ${total}`),
        h('div', { class: 'quiz-score-label' }, '正解'),
        score === total
          ? h('p', { style: 'color:var(--success);font-weight:700;margin:.5rem 0' }, '🎉 全問正解！素晴らしい！')
          : h('p', { style: 'color:var(--warn);margin:.5rem 0' }, `もう少し！間違えた問題を復習しましょう。`),
        h('div', { style: 'display:flex;gap:1rem;justify-content:center;margin-top:1rem;flex-wrap:wrap' },
          h('button', {
            class: 'btn btn-secondary',
            onclick: () => { currentIdx = 0; score = 0; answers.fill(null); render(); }
          }, '🔄 もう一度'),
          h('button', {
            class: 'btn btn-primary',
            onclick: async () => {
              try {
                await apiFetch(`/api/chapters/${chapterId}/lessons/${lessonId}/quiz/complete`, {
                  method: 'POST',
                  body: JSON.stringify({ score, total }),
                });
                showToast('進捗を保存しました ✓', 'success');
              } catch (_) {}
            }
          }, '進捗を保存')
        )
      )
    );
  }

  render();
  return section;
}

// ── ページ: 進捗 ─────────────────────────────

route('progress', async (_, root) => {
  $('#nav-progress')?.classList.add('active');

  const [chapters, progressData] = await Promise.all([
    apiFetch('/api/chapters'),
    apiFetch('/api/progress'),
  ]);

  const progressMap = {};
  for (const p of progressData.progress) progressMap[p.lesson_key] = p;

  const totalLessons = chapters.reduce((s, ch) => s + (ch.lessons?.length || 0), 0);
  const completedLessons = Object.values(progressMap).filter(p => p.completed).length;

  root.innerHTML = '';
  root.append(
    h('div', { class: 'progress-header' }, h('h1', {}, '🏆 あなたの進捗')),
    h('div', { class: 'progress-stats' },
      h('div', { class: 'stat-card' }, h('div', { class: 'stat-num' }, String(completedLessons)), h('div', { class: 'stat-label' }, '完了レッスン')),
      h('div', { class: 'stat-card' }, h('div', { class: 'stat-num' }, String(totalLessons)), h('div', { class: 'stat-label' }, '全レッスン')),
      h('div', { class: 'stat-card' }, h('div', { class: 'stat-num' }, `${totalLessons ? Math.round(completedLessons/totalLessons*100) : 0}%`), h('div', { class: 'stat-label' }, '達成率')),
      h('div', { class: 'stat-card' }, h('div', { class: 'stat-num' }, String(progressData.badges.length)), h('div', { class: 'stat-label' }, '獲得バッジ'))
    )
  );

  // バッジ
  const badgesSection = h('div', { class: 'badges-section' });
  badgesSection.append(h('h2', {}, '🎖️ バッジ'));
  if (progressData.badges.length === 0) {
    badgesSection.append(h('p', { class: 'no-badges' }, 'まだバッジがありません。レッスンを完了するとバッジをもらえます！'));
  } else {
    const grid = h('div', { class: 'badges-grid' });
    for (const badge of progressData.badges) {
      const [icon, ...labelParts] = badge.label.split(' ');
      grid.append(h('div', { class: 'badge-card' },
        h('div', { class: 'badge-icon' }, icon),
        h('div', { class: 'badge-label' }, labelParts.join(' '))
      ));
    }
    badgesSection.append(grid);
  }
  root.append(badgesSection);

  // 章ごとの進捗
  root.append(h('h2', { style: 'font-size:1rem;font-weight:700;color:var(--gray-500);margin-bottom:.75rem' }, '章別達成度'));
  for (const ch of chapters) {
    const lessonIds = ch.lessons || [];
    const done = lessonIds.filter(lid => progressMap[`${ch.id}/${lid}`]?.completed).length;
    const pct = lessonIds.length ? Math.round(done / lessonIds.length * 100) : 0;
    root.append(h('div', { class: 'progress-chapter' },
      h('div', { class: 'progress-chapter-header' },
        h('span', { class: 'progress-chapter-title' }, ch.title),
        h('span', { class: 'progress-pct' }, `${done}/${lessonIds.length} (${pct}%)`)
      ),
      h('div', { class: 'progress-bar' }, h('div', { class: 'progress-bar-fill', style: `width:${pct}%` }))
    ));
  }
});

// ── 初期化 ──────────────────────────────────

window.addEventListener('DOMContentLoaded', () => {
  const hash = location.hash || '#home';
  renderRoute(hash);
});
