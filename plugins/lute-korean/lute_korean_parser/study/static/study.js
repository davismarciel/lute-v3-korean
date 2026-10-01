/* Presentation only: observations still require an explicit, protected save. */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-observe]').forEach(button => {
    button.addEventListener('click', () => {
      const details = document.getElementById('quick-observation');
      if (!details) return;
      const form = details.querySelector('form');
      form.elements.item_id.value = button.dataset.observe;
      form.elements.event_type.value = button.dataset.event;
      form.elements.context.value = button.dataset.context;
      details.open = true;
      details.scrollIntoView({block: 'start', behavior: 'auto'});
      form.elements.context.focus();
    });
  });
});
