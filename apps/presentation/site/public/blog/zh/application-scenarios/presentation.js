const presentation = document.querySelector('#presentation');
presentation.hidden = false;
document.querySelector('.stage-buttons').hidden = false;
presentation.addEventListener('click', () => {
  const enabled = document.body.classList.toggle('presenting');
  presentation.setAttribute('aria-pressed', String(enabled));
  presentation.textContent = enabled ? '阅读模式' : '演讲模式';
});
const states = {
  pending: ['GitHub 返回当前修订的 checks pending。','记录 PR、修订与检查状态；相同观察无需制造新进展。','保留监控和恢复条件，等待结果。','按授权、预算和执行资格准入；等待范围之外的工作仍可推进。','没有重要变化时保持安静，避免把轮询变成催促。'],
  failed: ['当前修订的 CI 出现失败。','区分代码回归、环境故障和未知原因，保留证据。','提出一个有范围、有验收方式的修复后继。','重新检查执行者、写入范围与预算；获得资格后才执行。','把失败转成可接手的工作，而不只发一条报错消息。'],
  changed: ['PR 从修订 A 更新为修订 B。','原评审和测试绑定 A，不能直接证明 B 合格。','重新确认变更与验证范围，需要时重新评审。','保留版本关联和当前权限；旧回执不能冒充新结果。','让“通过”始终对应清楚的交付物。'],
  merged: ['GitHub 确认 PR 已合并。','记录终态和结果；合并不自动等于整个目标已完成。','检查目标验收：补集成验证、接续任务，或给出无后继理由。','结算当前监控与后继；发布等其他动作仍需相应授权。','每项工作有明确去向，完成后不凭惯性继续找活。']
};
document.querySelectorAll('[data-state]').forEach(button => button.addEventListener('click', () => {
  document.querySelectorAll('[data-state]').forEach(b => b.setAttribute('aria-pressed',String(b === button)));
  ['fact','domain','proposal','kernel','meaning'].forEach((id,i) => document.getElementById(id).textContent = states[button.dataset.state][i]);
}));
document.addEventListener('keydown', event => {
  if (!document.body.classList.contains('presenting') || event.altKey || event.ctrlKey || event.metaKey) return;
  if (event.key === 'Escape') { presentation.click(); return; }
  if (event.target.closest('input,textarea,select,[contenteditable=true]')) return;
  if (!['ArrowRight','ArrowLeft'].includes(event.key)) return;
  const sections = [...document.querySelectorAll('article > section')];
  let index = sections.findIndex(s => s.getBoundingClientRect().bottom > 100);
  index = Math.max(0, Math.min(sections.length - 1, index + (event.key === 'ArrowRight' ? 1 : -1)));
  event.preventDefault(); sections[index].scrollIntoView({behavior: 'instant'}); history.replaceState(null,'','#'+sections[index].id);
});
