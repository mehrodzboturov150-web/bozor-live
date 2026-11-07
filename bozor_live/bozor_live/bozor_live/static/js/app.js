/* Bozor.tj marketplace — browser UI. No build step and no third-party runtime. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const cats = [
    {name:'Автомобили',icon:'🚗',hint:'Легковые и внедорожники',bg:'#fff1e5'},
    {name:'Телефоны',icon:'📱',hint:'Смартфоны',bg:'#e8f0ff'},
    {name:'Недвижимость',icon:'🏡',hint:'Квартиры, дома',bg:'#fff0e7'},
    {name:'Электроника',icon:'💻',hint:'Техника',bg:'#f0eaff'},
    {name:'Мебель',icon:'🛋️',hint:'Для дома',bg:'#fff2dc'},
    {name:'Одежда',icon:'👟',hint:'Стиль и мода',bg:'#ffeaf0'},
    {name:'Работа',icon:'💼',hint:'Вакансии',bg:'#eaf3ff'},
    {name:'Услуги',icon:'🛠️',hint:'Мастера',bg:'#e5f5eb'},
    {name:'Другое',icon:'📦',hint:'Всё остальное',bg:'#f3f1e9'}
  ];
  const brands=['Toyota','Mercedes-Benz','BMW','Hyundai','Kia','Lexus','Honda','Nissan','Volkswagen','Audi','Opel','Daewoo','Chevrolet','Ford','Mazda','Subaru','Mitsubishi','Land Rover','Porsche','Tesla','BYD','Changan','Geely','Haval','Lada','Другая'];
  const cities = ['Душанбе','Худжанд','Бохтар','Куляб','Истаравшан','Турсунзаде','Пенджикент','Исфара','Канибадам','Другой город'];
  const state = {user:null,csrf:'',items:[],category:'',mode:'all',q:'',city:'',min:'',max:'',sort:'newest',page:1,pages:1,total:0,selected:null,authMode:'login',afterAuth:null,editing:null,chat:null,photoUrl:null,carBrand:'',carModel:'',yearFrom:'',yearTo:'',transmission:'',fuel:'',mileageMax:''};
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch]));
  const price = value => new Intl.NumberFormat('ru-RU').format(Number(value)||0) + ' сомони';
  const catIcon = name => cats.find(x=>x.name===name)?.icon || '📦';
  const icon = (id, klass='') => `<svg class="icon ${klass}" aria-hidden="true"><use href="#i-${id}"></use></svg>`;
  const safePhoto = url => typeof url==='string' && /^\/(media|static\/uploads)\/[a-zA-Z0-9._-]+$/.test(url) ? url : '';
  const place = v => `<span class="location-small">${icon('pin')}${esc(v)}</span>`;
  const cardDate = iso => {
    if (!iso) return '';
    const parsed = new Date(String(iso).replace(' ','T')+'Z');
    return Number.isNaN(parsed.getTime()) ? '' : new Intl.DateTimeFormat('ru-RU',{day:'numeric',month:'short'}).format(parsed);
  };
  let renderId = 0;

  async function api(url, options={}) {
    const method = (options.method||'GET').toUpperCase();
    const headers = {...(options.headers||{})};
    if (!['GET','HEAD','OPTIONS'].includes(method) && state.csrf) headers['X-CSRF-Token'] = state.csrf;
    let response;
    try { response = await fetch(url,{...options,headers,credentials:'same-origin'}); }
    catch (_err) { throw new Error('Нет соединения с сервером. Проверьте интернет.'); }
    const payload = await response.json().catch(()=>({error:'Ответ сервера не удалось прочитать'}));
    if (!response.ok) throw new Error(payload.error || `Ошибка сервера (${response.status})`);
    return payload;
  }
  const json = (method, data) => ({method,headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const toast = (message,error=false) => {
    const el = document.createElement('div');
    el.className = 'toast'+(error?' error':'');
    el.textContent = message;
    $('toastStack').appendChild(el);
    setTimeout(()=>el.remove(),4300);
  };
  const showError = err => toast(err?.message||String(err),true);
  const dialog = id => $(id);
  function openDialog(id) { document.querySelectorAll('dialog[open]').forEach(d=>d.close()); dialog(id).showModal(); }
  function closeDialogs() { document.querySelectorAll('dialog[open]').forEach(d=>d.close()); if(location.pathname.startsWith('/listing/')) history.replaceState({},'', '/'); }
  function requireUser(action) {
    if (state.user) return true;
    state.afterAuth = action || null;
    openAuth();
    return false;
  }

  function buildCategories() {
    $('categoryTiles').innerHTML = cats.map(c=>`<button class="category-tile ${state.category===c.name?'active':''}" data-action="category" data-category="${esc(c.name)}" aria-pressed="${state.category===c.name}"><span class="category-emoji" style="--tile-bg:${c.bg}">${c.icon}</span><span><span class="category-text">${esc(c.name)}</span><small class="category-small">${esc(c.hint)}</small></span></button>`).join('');
    $('categoryFilter').innerHTML = `<button class="side-cat ${!state.category?'active':''}" data-action="category" data-category="">${icon('grid')}Все категории</button>` + cats.map(c=>`<button class="side-cat ${state.category===c.name?'active':''}" data-action="category" data-category="${esc(c.name)}"><span class="side-cat-icon">${c.icon}</span>${esc(c.name)}</button>`).join('');
  }
  function fillSelects() {
    $('filterCity').innerHTML = '<option value="">Весь Таджикистан</option>' + cities.map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join('');
    $('postCity').innerHTML = '<option value="">Выберите город</option>' + cities.map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join('');
    $('postCategory').innerHTML = '<option value="">Выберите категорию</option>' + cats.map(c=>`<option value="${esc(c.name)}">${esc(c.name)}</option>`).join('');
    $('quickBrand').innerHTML += brands.map(b=>`<option value="${esc(b)}">${esc(b)}</option>`).join('');
    $('filterBrand').innerHTML += brands.map(b=>`<option value="${esc(b)}">${esc(b)}</option>`).join('');
    $('brandSuggestions').innerHTML = brands.map(b=>`<option value="${esc(b)}"></option>`).join('');
  }
  function updateAutoFilters(){
    const active = state.category === 'Автомобили';
    $('autoFilterBlock').hidden = !active;
    $('carPostFields').hidden = $('postCategory').value !== 'Автомобили';
  }
  function skeletons() {
    return Array.from({length:6},()=>`<div class="listing-skeleton"><div class="skeleton skeleton-img"></div><div class="skeleton skeleton-line"></div><div class="skeleton skeleton-line short"></div></div>`).join('');
  }
  function listingCard(x) {
    const src = safePhoto(x.photo);
    const car=x.category==='Автомобили';
    const summary=car?([x.car_year?String(x.car_year):'',x.car_mileage!=null?new Intl.NumberFormat('ru-RU').format(x.car_mileage)+' км':'',x.car_transmission||''].filter(Boolean).join(' · ')):'';
    return `<article class="listing-card ${car?'auto-listing-card':''}">
      <button type="button" class="listing-hit" data-action="detail" data-id="${x.id}" aria-label="Подробнее: ${esc(x.title)}">
      <div class="listing-image">${src?`<img src="${esc(src)}" alt="${esc(x.title)}" loading="lazy">`:`<span class="listing-placeholder">${catIcon(x.category)}</span>`}
        <span class="listing-tag">${esc(x.category)}</span></div>
      <div class="listing-info"><div class="listing-price">${price(x.price)}</div><h3 class="listing-title">${esc(x.title)}</h3>
        <div class="listing-specline">${esc(summary || (car?'Подробности в объявлении':''))}</div><div class="listing-meta">${place(x.city)}<span>${cardDate(x.created_at)}</span></div></div></button>
      <button class="favorite-button ${x.favorite?'active':''}" data-action="favorite" data-id="${x.id}" aria-label="${x.favorite?'Убрать из избранного':'Добавить в избранное'}" aria-pressed="${Boolean(x.favorite)}">${icon('heart')}</button>
    </article>`;
  }
  function urlParams() {
    const params = new URLSearchParams();
    if (state.q) params.set('q',state.q);
    if (state.category) params.set('category',state.category);
    if (state.city) params.set('city',state.city);
    if (state.min !== '') params.set('min_price',state.min);
    if (state.max !== '') params.set('max_price',state.max);
    if (state.sort!=='newest') params.set('sort',state.sort);
    if (state.category === 'Автомобили') {
      for (const [key,value] of Object.entries({brand:state.carBrand,model:state.carModel,year_from:state.yearFrom,year_to:state.yearTo,transmission:state.transmission,fuel:state.fuel,mileage_max:state.mileageMax})) if (value) params.set(key,value);
    }
    if (state.mode==='mine') params.set('mine','1');
    if (state.mode==='favorites') params.set('favorites','1');
    if (state.page>1) params.set('page',state.page);
    return params;
  }
  async function loadListings() {
    const seq = ++renderId;
    buildCategories();
    updateAutoFilters();
    $('listingGrid').innerHTML = skeletons();
    const headings = {all:state.category==='Автомобили'?'Автомобили в продаже':'Объявления Таджикистана',mine:'Мои объявления',favorites:'Избранное'};
    $('pageHeading').textContent = headings[state.mode];
    const badge = $('modeBadge');
    badge.hidden = state.mode==='all';
    badge.textContent = state.mode==='mine'?'Личный кабинет':'Сохранённое';
    try {
      const result = await api('/api/listings?'+urlParams());
      if (seq !== renderId) return;
      state.items = result.items;
      state.total = result.total;
      state.pages = result.pages;
      $('countLabel').textContent = `${state.total} ${plural(state.total,'объявление','объявления','объявлений')}`;
      $('resultSummary').textContent = state.mode==='mine' ? 'Управляйте вашими публикациями' : state.mode==='favorites' ? 'Здесь ваши понравившиеся предложения' : 'Находите предложения по отличным ценам';
      $('listingGrid').innerHTML = state.items.length ? state.items.map(listingCard).join('') : emptyContent();
      const p = $('pagination'); p.hidden = state.pages<=1;
      $('pageIndicator').textContent = `Страница ${state.page} из ${state.pages}`;
      document.querySelector('[data-action="prev-page"]').disabled = state.page<=1;
      document.querySelector('[data-action="next-page"]').disabled = state.page>=state.pages;
    } catch (err) {
      if (seq !== renderId) return;
      $('listingGrid').innerHTML = `<div class="empty-state"><span class="empty-icon">⚠️</span><h3>Не удалось загрузить объявления</h3><p>Попробуйте ещё раз.</p><button class="button button-primary" data-action="reload">Повторить</button></div>`;
      showError(err);
    }
  }
  function plural(n,one,two,many){const k=Math.abs(n)%100,v=k%10;return k>10&&k<20?many:v===1?one:v>=2&&v<=4?two:many;}
  function emptyContent() {
    const mine=state.mode==='mine';
    return `<div class="empty-state"><span class="empty-icon">${mine?'📦':state.mode==='favorites'?'💙':'🔎'}</span><h3>${mine?'Вы ещё ничего не опубликовали':state.mode==='favorites'?'Здесь появятся любимые объявления':'По вашему запросу ничего нет'}</h3><p>${mine?'Добавьте первое объявление — покупатели смогут его найти.':state.mode==='favorites'?'Нажимайте на сердечко у понравившихся товаров.':'Попробуйте выбрать другой город, категорию или изменить цену.'}</p><button class="button button-primary" data-action="${mine?'publish':'reset-filters'}">${mine?'Подать объявление':'Сбросить фильтры'}</button></div>`;
  }
  function goCatalog(){ $('catalog').scrollIntoView({behavior:'smooth',block:'start'}); }
  async function setMode(mode){ if ((mode==='mine'||mode==='favorites')&&!requireUser(mode))return;state.mode=mode;state.page=1;await loadListings();goCatalog();}
  async function setCategory(category){ state.category=category;state.mode='all';state.page=1;await loadListings();goCatalog(); }
  async function resetFilters(){state.category='';state.q='';state.city='';state.min='';state.max='';state.carBrand='';state.carModel='';state.yearFrom='';state.yearTo='';state.transmission='';state.fuel='';state.mileageMax='';state.sort='newest';state.mode='all';state.page=1;$('searchInput').value='';$('filterCity').value='';$('minPrice').value='';$('maxPrice').value='';$('sortSelect').value='newest';$('filterBrand').value='';$('filterModel').value='';$('filterYearFrom').value='';$('filterYearTo').value='';$('filterTransmission').value='';await loadListings();}
  function setAccountUI(){
    $('accountText').textContent = state.user ? state.user.username : 'Войти';
    $('accountText').title = state.user?.username||'';
  }
  async function refreshSession() {
    const result = await api('/api/me');
    state.user = result.user;
    state.csrf = result.csrf;
    setAccountUI();
  }
  function openAuth() {
    state.authMode='login'; renderAuth(); openDialog('authDialog');
  }
  function renderAuth() {
    const register = state.authMode==='register';
    $('authTitle').textContent=register?'Создать аккаунт':'Войти в аккаунт';
    $('authLead').textContent=register?'Присоединяйтесь к Bozor.tj и публикуйте объявления за пару минут.':'Войдите, чтобы публиковать объявления, сохранять находки и общаться с продавцами.';
    $('authSubmit').textContent=register?'Зарегистрироваться':'Войти';
    $('authSwitchText').innerHTML=register?'Уже есть аккаунт? <button class="inline-link" data-action="switch-auth">Войти</button>':'Нет аккаунта? <button class="inline-link" data-action="switch-auth">Зарегистрироваться</button>';
    $('authForm').elements.password.autocomplete=register?'new-password':'current-password';
  }
  async function onAuth(event) {
    event.preventDefault();
    const btn=$('authSubmit');btn.disabled=true;
    try {
      const data=Object.fromEntries(new FormData(event.currentTarget));
      const result=await api('/api/'+(state.authMode==='register'?'register':'login'),json('POST',data));
      state.user=result.user;state.csrf=result.csrf;
      setAccountUI();closeDialogs();$('authForm').reset();toast(state.authMode==='register'?'Аккаунт создан!':'Добро пожаловать!');
      const next=state.afterAuth;state.afterAuth=null;
      if (next==='publish') openPost();
      else if(next==='favorites'||next==='mine') setMode(next);
      else if(next==='inbox') openInbox();
      else if(next==='favorite') loadListings();
      else loadListings();
    }catch(err){showError(err);}finally{btn.disabled=false;}
  }
  async function logout() {
    try{const d=await api('/api/logout',{method:'POST'});state.user=null;state.csrf=d.csrf;closeDialogs();state.mode='all';setAccountUI();await loadListings();toast('Вы вышли из аккаунта');}catch(err){showError(err);}
  }
  function openAccount(){
    if (!state.user){openAuth();return;}
    $('accountBody').innerHTML=`<div class="account-welcome"><span class="seller-avatar">${esc(state.user.username.slice(0,1).toUpperCase())}</span><div><h3>${esc(state.user.username)}</h3><p>Участник сообщества Bozor.tj</p></div></div>
      <div class="account-links"><button data-action="mine">${icon('grid')}Мои объявления</button><button data-action="favorites">${icon('heart')}Избранное</button><button data-action="inbox">${icon('message')}Мои сообщения</button><button data-action="logout" class="logout">${icon('logout')}Выйти из аккаунта</button></div>`;
    openDialog('accountDialog');
  }
  function clearPhotoPreview() {
    if(state.photoUrl){URL.revokeObjectURL(state.photoUrl);state.photoUrl=null;}
    (state.photoUrls||[]).forEach(url=>URL.revokeObjectURL(url));state.photoUrls=[];
    $('photoPreview').hidden=true;$('photoPreview').innerHTML='';
  }
  function openPost(edit=null) {
    if (!requireUser('publish')) return;
    state.editing=edit;
    $('postForm').reset();clearPhotoPreview();
    $('postTitle').textContent=edit?'Редактировать объявление':'Новое объявление';
    $('postSubmit').textContent=edit?'Сохранить изменения':'Опубликовать объявление';
    $('removePhotoWrap').hidden=!Boolean(edit?.photo);
    if (edit) {
      const f=$('postForm');
      for(const name of ['title','price','category','city','description']) f.elements[name].value=edit[name] ?? '';
      for(const field of ['brand','model','year','mileage','transmission','fuel','drive','body','engine','color','steering','car_condition']) f.elements['car_'+field].value = edit['car_'+field] ?? '';
      const src=safePhoto(edit.photo);
      if(src){$('photoPreview').innerHTML=(edit.photos||[src]).map(p=>`<img src="${esc(safePhoto(p))}" alt="Текущая фотография">`).join('');$('photoPreview').hidden=false;}
    }
    updateAutoFilters();
    openDialog('postDialog');
  }
  async function onPost(event) {
    event.preventDefault();
    const btn=$('postSubmit');btn.disabled=true;btn.textContent='Сохраняем...';
    try {
      const body=new FormData(event.currentTarget);
      const isEdit=Boolean(state.editing);
      const url=isEdit?'/api/listings/'+state.editing.id:'/api/listings';
      const result=await api(url,{method:isEdit?'PATCH':'POST',body});
      closeDialogs();state.editing=null;clearPhotoPreview();state.mode='all';state.category='';state.page=1;
      await loadListings();toast(isEdit?'Объявление обновлено!':'Объявление опубликовано!');await openDetail(result.id);
    }catch(err){showError(err);}finally{btn.disabled=false;btn.textContent=state.editing?'Сохранить изменения':'Опубликовать объявление';}
  }
  function specEntry(label,value) {return value!==null&&value!==undefined&&String(value).trim()!=='' ? `<div class="spec-pair"><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>` : '';}
  function detailsMarkup(x) {
    const own=state.user?.id===x.owner_id;
    const photos=(x.photos||[x.photo]).map(safePhoto).filter(Boolean);
    const car=x.category==='Автомобили';
    const specs=car?[
      ['Марка',x.car_brand],['Модель',x.car_model],['Год выпуска',x.car_year],
      ['Пробег',x.car_mileage!=null?new Intl.NumberFormat('ru-RU').format(x.car_mileage)+' км':null],
      ['Коробка передач',x.car_transmission],['Тип топлива',x.car_fuel],['Привод',x.car_drive],
      ['Тип кузова',x.car_body],['Двигатель',x.car_engine],['Цвет',x.car_color],
      ['Расположение руля',x.car_steering],['Состояние',x.car_car_condition]
    ].map(([label,value])=>specEntry(label,value)).join(''):'';
    const main=photos[0]||'';
    return `<div class="listing-breadcrumb">Bozor.tj / ${esc(x.category)} / ${esc(x.city)}</div>
      <div class="detail-big-head"><div><span class="detail-category">${esc(x.category)}</span><h2>${esc(x.title)}</h2><div class="detail-location">${icon('pin')}${esc(x.city)} <span>· Объявление №${x.id} · ${cardDate(x.created_at)}</span></div></div></div>
      <div class="detail-layout new-detail-layout">
        <div class="detail-primary">
          <div class="detail-gallery"><div class="detail-image" id="galleryMain">${main?`<img src="${esc(main)}" alt="${esc(x.title)}">`:`<div class="detail-image-fallback">${catIcon(x.category)}<span>Фото пока нет</span></div>`}</div>
            ${photos.length>1?`<div class="gallery-thumbs">${photos.map((url,i)=>`<button type="button" class="gallery-thumb ${i===0?'selected':''}" data-action="preview-photo" data-src="${esc(url)}" aria-label="Фото ${i+1}"><img src="${esc(url)}" alt="Фото ${i+1}"></button>`).join('')}</div>`:''}
          </div>
          <section class="ad-section"><h3>${car?'Характеристики автомобиля':'Информация об объявлении'}</h3>
            ${specs?`<dl class="spec-grid">${specs}</dl>`:`<div class="specs-empty">${car?'Продавец пока не указал дополнительные характеристики. Спросите их в чате.':'Категория: '+esc(x.category)}</div>`}</section>
          <section class="ad-section"><h3>Описание продавца</h3><p class="full-description">${esc(x.description)}</p></section>
          <section class="ad-section"><h3>Местоположение</h3><div class="location-block">${icon('pin')} ${esc(x.city)}, Таджикистан</div></section>
        </div>
        <aside class="detail-aside"><div class="detail-aside-card"><div class="aside-caption">Цена</div><div class="detail-price">${price(x.price)}</div>
            <div class="price-note">Уточняйте наличие и условия у продавца</div>
            <div class="seller-card"><div class="seller-avatar">${esc(String(x.seller).slice(0,1).toUpperCase())}</div><div><small>Продавец</small><strong>${esc(x.seller)}</strong><span class="seller-role">Пользователь Bozor.tj</span></div></div>
            <div class="detail-actions">${own?`<button class="button button-primary" data-action="edit-listing" data-id="${x.id}">${icon('edit')} Изменить объявление</button><button class="button button-outline" data-action="delete-listing" data-id="${x.id}">${icon('trash')} Удалить</button>`:`<button class="button button-primary" data-action="open-chat" data-id="${x.id}" data-partner="${x.owner_id}">${icon('message')} Написать продавцу</button><button class="button button-outline" data-action="favorite" data-id="${x.id}">${icon('heart')} ${x.favorite?'Убрать из избранного':'В избранное'}</button>`}</div>
          </div><div class="safety-card">${icon('shield')}<div><strong>Покупайте безопасно</strong><p>Осмотрите товар лично, проверяйте документы и не отправляйте предоплату незнакомым людям.</p></div></div></aside>
      </div>`;
  }
  async function openDetail(id, push=true) {
    try {
      const {item:x}=await api('/api/listings/'+id);state.selected=x;
      $('detailTitle').textContent=x.title;
      $('detailBody').innerHTML=detailsMarkup(x);
      openDialog('detailDialog');
      if(push && location.pathname!=='/listing/'+id) history.pushState({listing:id},'', '/listing/'+id);
    }catch(err){showError(err);}
  }
  async function favorite(id) {
    if(!requireUser('favorite'))return;
    try {
      const data=await api('/api/favorites/'+id,{method:'POST'});
      const existing=state.items.find(x=>x.id===id);if(existing)existing.favorite=data.favorite?1:0;
      if(state.selected?.id===id){state.selected.favorite=data.favorite?1:0;await openDetail(id);}
      else await loadListings();
      toast(data.favorite?'Добавлено в избранное':'Убрано из избранного');
    }catch(err){showError(err);}
  }
  async function removeListing(id) {
    if(!confirm('Удалить это объявление? Это действие нельзя отменить.'))return;
    try{await api('/api/listings/'+id,{method:'DELETE'});closeDialogs();await loadListings();toast('Объявление удалено');}catch(err){showError(err);}
  }
  async function openInbox() {
    if (!requireUser('inbox')) return;
    try {
      const {items}=await api('/api/conversations');
      $('inboxBody').innerHTML = items.length?items.map(x=>`<button class="inbox-row" data-action="open-chat" data-id="${x.listing_id}" data-partner="${x.partner_id}"><span class="inbox-avatar">${icon('message')}</span><span><strong>${esc(x.title)}</strong><small>Собеседник: ${esc(x.partner)}</small></span>${icon('arrow','inbox-arrow')}</button>`).join(''):`<div class="dialog-empty"><span class="empty-icon">💬</span><p>Чатов пока нет. Откройте объявление и напишите продавцу.</p></div>`;
      openDialog('inboxDialog');
    }catch(err){showError(err);}
  }
  async function openChat(id,partner) {
    if (!requireUser('inbox')) return;
    if(partner===state.user.id){await openInbox();return;}
    try {
      const query=partner?'?partner='+encodeURIComponent(partner):'';
      const [messages, listing] = await Promise.all([api('/api/messages/'+id+query),api('/api/listings/'+id)]);
      state.chat={id,partner:messages.partner};
      $('chatTitle').textContent=listing.item.title;
      $('chatMessages').innerHTML=messages.items.length?messages.items.map(m=>`<div class="chat-bubble ${m.sender_id===state.user.id?'mine':''}"><small>${esc(m.sender)}</small>${esc(m.body).replace(/\n/g,'<br>')}</div>`).join(''):`<div class="dialog-empty">Начните переписку с продавцом 👋</div>`;
      $('chatForm').reset();openDialog('chatDialog');$('chatMessages').scrollTop=$('chatMessages').scrollHeight;
    }catch(err){showError(err);}
  }
  async function sendMessage(event) {
    event.preventDefault();if(!state.chat)return;
    const field=event.currentTarget.elements.body;const body=field.value.trim();if(!body)return;
    try {
      await api('/api/messages/'+state.chat.id,json('POST',{body,partner:state.chat.partner}));
      const {id,partner}=state.chat;await openChat(id,partner);
    }catch(err){showError(err);}
  }
  function closeFilterOnMobile(){ if(window.innerWidth<=650) $('filtersPanel').classList.remove('open'); }
  async function onAction(action,node) {
    const id=Number(node.dataset.id);
    switch(action) {
      case 'autosearch':closeDialogs();state.category='Автомобили';state.mode='all';state.page=1;await loadListings();goCatalog();break;
      case 'quick-autosearch':state.category='Автомобили';state.carBrand=$('quickBrand').value;state.carModel=$('quickModel').value.trim();state.yearFrom=$('quickYear').value;state.max=$('quickPrice').value;state.mode='all';state.page=1;$('filterBrand').value=state.carBrand;$('filterModel').value=state.carModel;$('filterYearFrom').value=state.yearFrom;$('maxPrice').value=state.max;await loadListings();goCatalog();break;
      case 'preview-photo':{const url=safePhoto(node.dataset.src);if(url){$('galleryMain').innerHTML=`<img src="${esc(url)}" alt="Фото объявления">`;document.querySelectorAll('.gallery-thumb').forEach(b=>b.classList.toggle('selected',b===node));}break;}
      case 'home':closeDialogs();await resetFilters();window.scrollTo({top:0,behavior:'smooth'});break;
      case 'category':await setCategory(node.dataset.category||'');closeFilterOnMobile();break;
      case 'clear-category':await setCategory('');break;
      case 'favorites':closeDialogs();await setMode('favorites');break;
      case 'mine':closeDialogs();await setMode('mine');break;
      case 'inbox':await openInbox();break;
      case 'account':openAccount();break;
      case 'publish':openPost();break;
      case 'detail':await openDetail(id);break;
      case 'favorite':await favorite(id);break;
      case 'open-chat':await openChat(id,Number(node.dataset.partner));break;
      case 'edit-listing':openPost(state.selected);break;
      case 'delete-listing':await removeListing(id);break;
      case 'switch-auth':state.authMode=state.authMode==='login'?'register':'login';renderAuth();break;
      case 'logout':await logout();break;
      case 'reset-filters':await resetFilters();closeFilterOnMobile();break;
      case 'apply-filters':state.city=$('filterCity').value;state.min=$('minPrice').value;state.max=$('maxPrice').value;state.carBrand=$('filterBrand').value;state.carModel=$('filterModel').value.trim();state.yearFrom=$('filterYearFrom').value;state.yearTo=$('filterYearTo').value;state.transmission=$('filterTransmission').value;state.page=1;await loadListings();closeFilterOnMobile();break;
      case 'toggle-filters':$('filtersPanel').classList.toggle('open');break;
      case 'prev-page':if(state.page>1){state.page--;await loadListings();goCatalog();}break;
      case 'next-page':if(state.page<state.pages){state.page++;await loadListings();goCatalog();}break;
      case 'reload':await loadListings();break;
      case 'how':closeDialogs();$('howItWorks').scrollIntoView({behavior:'smooth'});break;
    }
  }
  function bindEvents() {
    document.addEventListener('click',async event=>{
      const close=event.target.closest('[data-close]');
      if(close){dialog(close.dataset.close).close();if(close.dataset.close==='detailDialog'&&location.pathname.startsWith('/listing/'))history.replaceState({},'', '/');return;}
      const node=event.target.closest('[data-action]');
      if(node){event.preventDefault();try{await onAction(node.dataset.action,node);}catch(err){showError(err);}}
    });
    document.querySelectorAll('dialog').forEach(d=>{d.addEventListener('click',event=>{if(event.target===d)d.close();});d.addEventListener('close',()=>{if(d.id==='detailDialog'&&location.pathname.startsWith('/listing/'))history.replaceState({},'', '/');});});
    window.addEventListener('popstate',()=>{const m=location.pathname.match(/^\/listing\/(\d+)$/);if(m)openDetail(Number(m[1]),false);else if($('detailDialog').open)$('detailDialog').close();});
    $('postCategory').addEventListener('change',updateAutoFilters);
    $('searchForm').addEventListener('submit',async e=>{e.preventDefault();state.q=$('searchInput').value.trim();state.page=1;state.mode='all';await loadListings();goCatalog();});
    $('authForm').addEventListener('submit',onAuth);
    $('postForm').addEventListener('submit',onPost);
    $('chatForm').addEventListener('submit',sendMessage);
    $('sortSelect').addEventListener('change',async e=>{state.sort=e.target.value;state.page=1;await loadListings();});
    $('postPhoto').addEventListener('change',e=>{
      clearPhotoPreview();const files=[...e.target.files];if(!files.length)return;
      if(files.length>6 || files.some(f=>f.size>5*1024*1024)){e.target.value='';toast('До 6 фотографий, каждая до 5 МБ',true);return;}
      state.photoUrls=files.map(f=>URL.createObjectURL(f));
      $('photoPreview').hidden=false;
      for(const url of state.photoUrls){const img=document.createElement('img');img.src=url;img.alt='Предпросмотр фотографии';$('photoPreview').appendChild(img);}
    });
    $('year').textContent=new Date().getFullYear();
  }
  async function init() {
    fillSelects();buildCategories();bindEvents();
    try{await refreshSession();}catch(err){showError(err);}
    await loadListings();
    const m=location.pathname.match(/^\/listing\/(\d+)$/);if(m)await openDetail(Number(m[1]),false);
  }
  init();
})();
