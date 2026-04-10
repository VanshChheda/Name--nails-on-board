// Nails on Board — Main JS

// ── Dark mode ──
(function(){
  const t = localStorage.getItem('theme') || 'light';
  document.documentElement.setAttribute('data-theme', t);
  const btn = document.getElementById('darkToggle');
  if(btn) btn.textContent = t === 'dark' ? '☀️' : '🌙';
})();

document.getElementById('darkToggle')?.addEventListener('click', function(){
  const h = document.documentElement;
  const now = h.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  h.setAttribute('data-theme', now);
  localStorage.setItem('theme', now);
  this.textContent = now === 'dark' ? '☀️' : '🌙';
});

// ── Mobile nav ──
const navToggle = document.getElementById('navToggle');
const mobileNav = document.getElementById('mobileNav');
if(navToggle && mobileNav){
  navToggle.addEventListener('click', () => {
    navToggle.classList.toggle('open');
    mobileNav.classList.toggle('open');
  });
  document.addEventListener('click', e => {
    if(!navToggle.contains(e.target) && !mobileNav.contains(e.target)){
      navToggle.classList.remove('open');
      mobileNav.classList.remove('open');
    }
  });
}

// ── Auto-dismiss flash ──
document.querySelectorAll('.flash').forEach(el => {
  setTimeout(() => { el.style.opacity='0'; setTimeout(()=>el.remove(),400); }, 5000);
});

// ── Scroll-in animation ──
if('IntersectionObserver' in window){
  const io = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if(e.isIntersecting){ e.target.style.opacity='1'; e.target.style.transform='translateY(0)'; io.unobserve(e.target); }
    });
  }, {threshold:0.08});
  document.querySelectorAll('.product-card,.feature-card,.gallery-item,.track-card').forEach((el,i)=>{
    el.style.cssText += `opacity:0;transform:translateY(18px);transition:opacity .4s ease ${i*.04}s,transform .4s ease ${i*.04}s`;
    io.observe(el);
  });
}

// ── Min date on appointment ──
const di = document.querySelector('input[type=date]');
if(di) di.min = new Date().toISOString().split('T')[0];

// ── UPI copy ──
window.copyUPI = function(){
  const t = document.getElementById('upiIdText')?.textContent;
  if(!t) return;
  navigator.clipboard.writeText(t).then(()=>{
    const b = document.querySelector('.copy-btn');
    if(b){b.textContent='✅ Copied!'; setTimeout(()=>b.textContent='📋 Copy',2000);}
  });
};

// ── Hide UPI deep link on desktop ──
if(!/Android|iPhone|iPad/i.test(navigator.userAgent)){
  const ub = document.getElementById('upiPayBtn');
  if(ub) ub.style.display='none';
}
