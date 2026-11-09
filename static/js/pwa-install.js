// PWA Installation & Service Worker Registration Handler
(function () {
  'use strict';

  let deferredPrompt = null;
  const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;

  // 1. Register Service Worker
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js', { scope: '/' })
        .then((reg) => {
          console.log('[PWA] ServiceWorker registered with scope:', reg.scope);
        })
        .catch((err) => {
          console.warn('[PWA] ServiceWorker registration failed:', err);
        });
    });
  }

  // 2. UI Elements
  function getElements() {
    return {
      sidebarBtn: document.getElementById('sidebarInstallBtn'),
      settingsCard: document.getElementById('settingsInstallCard'),
      settingsBtn: document.getElementById('settingsInstallBtn'),
      settingsRow: document.getElementById('settingsInstallRow'),
    };
  }

  function updateInstallUI() {
    const { sidebarBtn, settingsCard } = getElements();

    if (isStandalone) {
      // App is already installed and running in standalone mode
      if (sidebarBtn) sidebarBtn.style.display = 'none';
      if (settingsCard) settingsCard.style.display = 'none';
      return;
    }

    // Always keep visible if not already standalone
    if (sidebarBtn) {
      sidebarBtn.style.display = 'flex';
    }
    if (settingsCard) {
      settingsCard.style.display = 'block';
    }
  }

  // 3. Capture beforeinstallprompt
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    console.log('[PWA] beforeinstallprompt captured');
    updateInstallUI();
  });

  // 4. Handle App Installed
  window.addEventListener('appinstalled', () => {
    console.log('[PWA] App successfully installed');
    deferredPrompt = null;
    const { sidebarBtn, settingsCard } = getElements();
    if (sidebarBtn) sidebarBtn.style.display = 'none';
    if (settingsCard) settingsCard.style.display = 'none';
  });

  // 5. Trigger Install Process
  async function triggerInstall() {
    if (deferredPrompt) {
      deferredPrompt.prompt();
      const choiceResult = await deferredPrompt.userChoice;
      if (choiceResult.outcome === 'accepted') {
        console.log('[PWA] User accepted the install prompt');
        deferredPrompt = null;
        updateInstallUI();
      } else {
        console.log('[PWA] User dismissed the install prompt');
      }
    } else if (isIOS) {
      showIOSInstructions();
    } else {
      // Fallback modal with guide for user's browser
      showGenericInstructions();
    }
  }

  // 6. iOS Instructions Modal
  function showIOSInstructions() {
    let modal = document.getElementById('pwaIOSModal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'pwaIOSModal';
      modal.className = 'pwa-modal-overlay';
      modal.innerHTML = `
        <div class="pwa-modal-content">
          <div class="pwa-modal-header">
            <h3>Install CalamanSense</h3>
            <button type="button" class="pwa-modal-close" id="closePwaIOSModal">&times;</button>
          </div>
          <div class="pwa-modal-body">
            <p style="margin-top:0;">To install CalamanSense on your iPhone or iPad:</p>
            <ol class="pwa-ios-steps">
              <li>Tap the <strong>Share</strong> button <span class="material-symbols-outlined" style="vertical-align:middle;font-size:20px;">ios_share</span> in Safari's bottom toolbar.</li>
              <li>Scroll down the menu and tap <strong>Add to Home Screen</strong> <span class="material-symbols-outlined" style="vertical-align:middle;font-size:20px;">add_box</span>.</li>
              <li>Tap <strong>Add</strong> in the top right corner.</li>
            </ol>
          </div>
          <button type="button" class="pwa-modal-done-btn" id="donePwaIOSModal">Got it</button>
        </div>
      `;
      document.body.appendChild(modal);

      const close = () => { modal.style.display = 'none'; };
      modal.querySelector('#closePwaIOSModal').addEventListener('click', close);
      modal.querySelector('#donePwaIOSModal').addEventListener('click', close);
      modal.addEventListener('click', (e) => {
        if (e.target === modal) close();
      });
    }
    modal.style.display = 'flex';
  }

  // Generic Instructions Modal
  function showGenericInstructions() {
    let modal = document.getElementById('pwaGenericModal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'pwaGenericModal';
      modal.className = 'pwa-modal-overlay';
      modal.innerHTML = `
        <div class="pwa-modal-content">
          <div class="pwa-modal-header">
            <h3>Install CalamanSense</h3>
            <button type="button" class="pwa-modal-close" id="closePwaGenericModal">&times;</button>
          </div>
          <div class="pwa-modal-body">
            <p style="margin-top:0;">To install CalamanSense on your device:</p>
            <ol class="pwa-ios-steps">
              <li>Open your browser options menu (tap <strong>⋮</strong> or <strong>⋯</strong> in the corner).</li>
              <li>Select <strong>Install app</strong> or <strong>Add to Home screen</strong>.</li>
              <li>Confirm installation when prompted.</li>
            </ol>
            <p style="font-size:12px;color:var(--gray);margin-bottom:0;">On Desktop: You can also click the <strong>Install icon</strong> in your browser's address bar.</p>
          </div>
          <button type="button" class="pwa-modal-done-btn" id="donePwaGenericModal" style="margin-top:16px;">Got it</button>
        </div>
      `;
      document.body.appendChild(modal);

      const close = () => { modal.style.display = 'none'; };
      modal.querySelector('#closePwaGenericModal').addEventListener('click', close);
      modal.querySelector('#donePwaGenericModal').addEventListener('click', close);
      modal.addEventListener('click', (e) => {
        if (e.target === modal) close();
      });
    }
    modal.style.display = 'flex';
  }

  // 7. Bind click listeners once DOM is loaded
  document.addEventListener('DOMContentLoaded', () => {
    updateInstallUI();

    const { sidebarBtn, settingsBtn, settingsRow } = getElements();

    if (sidebarBtn) {
      sidebarBtn.addEventListener('click', (e) => {
        e.preventDefault();
        triggerInstall();
      });
    }

    if (settingsBtn) {
      settingsBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        triggerInstall();
      });
    }

    if (settingsRow) {
      settingsRow.addEventListener('click', (e) => {
        if (e.target !== settingsBtn && !settingsBtn.contains(e.target)) {
          triggerInstall();
        }
      });
    }
  });

  window.triggerPWAInstall = triggerInstall;
})();
