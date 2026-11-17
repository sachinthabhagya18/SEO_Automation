window.metadataPreview = function () {
  const data = JSON.parse(document.getElementById('metadata-preview-data').textContent);
  return {
    mode: 'preview', ...data, tab: 'google', copied: false, imageFailed: false, metadataStatus: '', loadSequence: 0, savedReady: false,
    init() {
      const form = document.querySelector('[data-metadata-editor]');
      if (form) { form.addEventListener('input', () => this.readForm()); this.readForm(); }
      if (form && data.mode === 'new') {
        const page = document.getElementById('id_page');
        page?.addEventListener('change', () => this.loadMetadata());
        this.loadMetadata();
      }
    },
    async loadMetadata(force = false) {
      const page = document.getElementById('id_page');
      if (!page?.value || data.mode !== 'new') return;
      const sequence = ++this.loadSequence;
      this.savedReady = false;
      const endpoint = '/sites/' + this.site_id + '/pages/' + page.value + '/metadata/';
      this.metadataStatus = 'Reading saved metadata...';
      const update = result => {
        if (sequence !== this.loadSequence) return;
        if (result.ready) {
          // Existing user text is never replaced by a delayed network response.
          data.title = result.stored.title || result.page_title || '';
          data.description = result.stored.description || '';
          data.base_page_id = page.value;
          this.savedReady = true;
          this.readForm();
          this.metadataStatus = 'Saved metadata read: ' + new Date(result.read_at).toLocaleString();
        }
      };
      const read = async () => {
        const response = await fetch(endpoint, {credentials: 'same-origin', cache: 'no-store'});
        if (!response.ok) throw new Error('read_failed');
        return response.json();
      };
      try {
        const cached = await read();
        if (sequence !== this.loadSequence) return;
        update(cached);
        if (!force && cached.ready && Date.now() - Date.parse(cached.read_at) < 300000) return;
        const token = document.querySelector('[data-metadata-editor] input[name=csrfmiddlewaretoken]').value;
        const response = await fetch(endpoint + 'refresh/', {method:'POST', credentials:'same-origin', headers:{'X-CSRFToken':token}});
        if (!response.ok) throw new Error('refresh_failed');
        this.metadataStatus = cached.ready ? this.metadataStatus + ' (refreshing in background)' : 'WordPress metadata is loading in background...';
        for (let attempt = 0; attempt < 35; attempt++) {
          await new Promise(resolve => setTimeout(resolve, 2000));
          if (sequence !== this.loadSequence) return;
          const result = await read();
          if (['failed','cancelled'].includes(result.state)) throw new Error('refresh_failed');
          if (result.state === 'ready') { update(result); return; }
        }
        this.metadataStatus = 'Still loading. You can keep editing and refresh again later.';
      } catch {
        if (sequence === this.loadSequence) this.metadataStatus = 'Could not refresh saved metadata. Check the WordPress connection; your draft text is preserved.';
      }
    },
    useSavedMetadata() {
      if (!this.savedReady || data.mode !== 'new') return;
      const page = document.getElementById('id_page');
      if (page?.value !== data.base_page_id) return;
      document.getElementById('id_proposed_title').value = data.title;
      document.getElementById('id_proposed_description').value = data.description;
      this.readForm();
    },
    readForm() {
      const page = document.getElementById('id_page');
      if (page && data.page_urls?.[page.value]) this.url = data.page_urls[page.value];
      const title = document.getElementById('id_proposed_title');
      const desc = document.getElementById('id_proposed_description');
      const titleFlag = document.getElementById('id_change_title');
      const descFlag = document.getElementById('id_change_description');
      if (title) this.title = !titleFlag || titleFlag.checked ? title.value : (page && page.value !== data.base_page_id ? data.page_titles?.[page.value] || data.title : data.title);
      if (desc) this.description = !descFlag || descFlag.checked ? desc.value : data.description;
      const plainTitle = document.getElementById('id_title');
      const plainDesc = document.getElementById('id_description');
      const image = document.getElementById('id_image_url');
      if (plainTitle) this.title = plainTitle.value;
      if (plainDesc) this.description = plainDesc.value;
      if (image) { this.image_url = image.value; this.imageFailed = false; }
    },
    get domain() { try { return new URL(this.url).hostname; } catch { return ''; } },
    get imageSrc() { return '/sites/' + this.site_id + '/preview/image/?url=' + encodeURIComponent(this.image_url); },
    get code() {
      const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
      return '<title>' + escape(this.title) + '</title>\n<meta name="description" content="' + escape(this.description) + '">\n<meta property="og:title" content="' + escape(this.title) + '">\n<meta property="og:description" content="' + escape(this.description) + '">' + (this.image_url ? '\n<meta property="og:image" content="' + escape(this.image_url) + '">' : '');
    },
    async copyCode() { try { await navigator.clipboard.writeText(this.code); this.copied = true; } catch { this.copied = false; } }
  };
};

window.changeProgress = function(endpoint,initial) {
  return {
    state:initial, notice:'',
    async init() {
      const active=['queued','applying','restoring','restoration_queued','applied_pending_verification'];
      if (!active.includes(initial)) return;
      this.notice='Worker is processing this draft. Status updates automatically.';
      for (let count=0;count<60;count++) {
        await new Promise(resolve=>setTimeout(resolve,2000));
        try {
          const response=await fetch(endpoint,{credentials:'same-origin',cache:'no-store'});
          if (!response.ok) throw new Error();
          const result=await response.json();this.state=result.state;
          if (!active.includes(result.state)) { window.location.reload();return; }
        } catch {this.notice='Status unavailable. Use Refresh status to check again.';return;}
      }
      this.notice='Still processing. Use Refresh status to check again; do not resubmit approval.';
    }
  };
};
