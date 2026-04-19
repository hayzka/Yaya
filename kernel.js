/* AMONSPATH OS v15.0 | MODULE 2: DATA & IDENTITY KERNEL
  Logic: Identity Persistence, Security Gate, Data Transformation
*/

const Kernel = {
    // 1. IDENTITY PERSISTENCE (Invisible Identity)
    async establishConnection() {
        const user = window.Telegram.WebApp.initDataUnsafe.user || { id: 0 };
        console.log("[KERNEL] INITIALIZING_NODE_ID:", user.id);

        try {
            const { data, error } = await Core.db
                .from('profiles')
                .select('*')
                .eq('telegram_id', user.id)
                .single();

            if (data) {
                Core.state.profile = data;
                this.syncIdentityUI(data);
                ThemeEngine.apply(data.theme_color);
            } else {
                console.warn("[KERNEL] GHOST_MODE_ACTIVE");
            }
        } catch (err) {
            console.error("[FATAL] CONNECTION_REFUSED", err);
        }
    },

    // 2. DATA STREAMING (Real-time & Batching)
    async fetchArchive() {
        UI.showShimmer(true);
        let query = Core.db.from('music_posts').select('*, profiles(*)').order('created_at', {ascending: false});
        
        if(Core.state.view === 'mine') {
            query = query.eq('sender_id', Core.state.user.id);
        }

        const { data, error } = await query;
        if (error) return UI.notify("ERR: DATA_SYNC_FAILED");

        const viewport = document.getElementById('viewport');
        viewport.innerHTML = ''; // Clear current

        data.forEach((node, index) => {
            const element = this.constructNode(node);
            element.style.animationDelay = `${index * 0.1}s`;
            viewport.appendChild(element);
        });
        UI.showShimmer(false);
    },

    // 3. NODE CONSTRUCTOR (DOM Logic)
    constructNode(n) {
        const div = document.createElement('article');
        div.className = 'music-node animate-node';
        div.innerHTML = `
            <div class="node-header" style="padding: 15px 20px; display: flex; align-items: center; gap: 12px;">
                <img src="${n.profiles.photo_url}" style="width: 32px; height: 32px; border-radius: 10px; border: var(--border);">
                <div>
                    <h4 style="font-size: 13px;">${n.profiles.display_name}</h4>
                    <p class="font-mono" style="font-size: 8px; color: var(--accent);">@${n.profiles.username}</p>
                </div>
            </div>
            <div class="artwork-wrapper">
                <img src="${n.music_cover}" loading="lazy">
                <button class="play-overlay" onclick="AudioEngine.toggle('${n.music_url}', this)">▶</button>
            </div>
            <div class="node-details">
                <h3 class="font-heavy">${n.music_title}</h3>
                <p>${n.caption || ''}</p>
            </div>
        `;
        return div;
    }
};
