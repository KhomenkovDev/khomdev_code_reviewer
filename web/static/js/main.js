document.addEventListener('DOMContentLoaded', () => {
    // State
    let currentSessionId = null;

    // Elements
    const githubForm = document.getElementById('github-form');
    const localForm = document.getElementById('local-form');
    const localFilesInput = document.getElementById('local-files');
    const dropZone = document.getElementById('drop-zone');
    
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatBtn = document.getElementById('chat-btn');
    const chatDisplay = document.getElementById('chat-display');
    const statusIndicator = document.getElementById('status-indicator');
    
    const loadingOverlay = document.getElementById('loading-overlay');
    const loadingText = document.getElementById('loading-text');

    // UI Helpers
    const setStatus = (isReady, text) => {
        if (isReady) {
            statusIndicator.innerHTML = '<i class="fa-solid fa-circle-check" style="color: #4ec9b0;"></i> <span>Ready</span>';
            chatInput.disabled = false;
            chatBtn.disabled = false;
        } else {
            statusIndicator.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin" style="color: #6366f1;"></i> <span>' + text + '</span>';
            chatInput.disabled = true;
            chatBtn.disabled = true;
        }
    };

    const showLoading = (text) => {
        loadingText.innerText = text;
        loadingOverlay.classList.add('active');
        setStatus(false, "Working...");
    };

    const hideLoading = () => {
        loadingOverlay.classList.remove('active');
        setStatus(true, "Ready");
    };

    const appendMessage = (sender, htmlContent, roleClass) => {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${roleClass}`;
        
        let icon = '';
        if(roleClass === 'system') icon = '<i class="fa-solid fa-robot"></i>';
        else if(roleClass === 'user') icon = '<i class="fa-solid fa-user"></i>';
        else if(roleClass === 'ai') icon = '<i class="fa-solid fa-brain"></i>';
        
        msgDiv.innerHTML = `
            <div class="msg-header">${icon} ${sender}</div>
            <div class="msg-body">${htmlContent}</div>
        `;
        
        chatDisplay.appendChild(msgDiv);
        
        // Scroll to bottom
        chatDisplay.scrollTop = chatDisplay.scrollHeight;
        
        // Apply syntax highlighting
        document.querySelectorAll('pre code').forEach((block) => {
            hljs.highlightElement(block);
        });
    };

    // --- GitHub Form Submit ---
    githubForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const url = document.getElementById('repo-url').value;
        if (!url) return;

        showLoading('Cloning repository and analyzing codebase. This may take a few minutes...');
        
        const formData = new FormData();
        formData.append('repo_url', url);

        try {
            const res = await fetch('/api/load-github', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            
            if (data.status === 'success') {
                currentSessionId = data.session_id;
                appendMessage('AI Reviewer', data.html_review, 'ai');
            } else {
                appendMessage('System Error', data.message || 'Failed to load GitHub repository.', 'system');
            }
        } catch (err) {
            appendMessage('System Error', err.message, 'system');
        } finally {
            hideLoading();
        }
    });

    // --- Local Files ---
    localFilesInput.addEventListener('change', async (e) => {
        const files = e.target.files;
        if (files.length === 0) return;
        await handleFiles(files);
        localFilesInput.value = ""; // reset
    });

    // Drag and drop setup for Dropzone
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.add('dragover'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.remove('dragover'), false);
    });

    dropZone.addEventListener('drop', async (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            await handleFiles(files);
        }
    });

    async function handleFiles(files) {
        showLoading('Uploading files and analyzing codebase...');
        
        const formData = new FormData();
        for (let i = 0; i < files.length; i++) {
            formData.append('files', files[i]);
        }

        try {
            const res = await fetch('/api/load-local', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            
            if (data.status === 'success') {
                currentSessionId = data.session_id;
                appendMessage('AI Reviewer', data.html_review, 'ai');
            } else {
                appendMessage('System Error', data.message || 'Failed to analyze files.', 'system');
            }
        } catch (err) {
            appendMessage('System Error', err.message, 'system');
        } finally {
            hideLoading();
        }
    }

    // --- Chat Form Submit ---
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const msg = chatInput.value.trim();
        if (!msg) return;

        if (!currentSessionId) {
            alert("No active session. Please load a GitHub repo or local folder first.");
            return;
        }

        // Display user message instantly
        appendMessage('You', `<p>${msg.replace(/(?:\r\n|\r|\n)/g, '<br>')}</p>`, 'user');
        chatInput.value = '';
        
        setStatus(false, "Thinking...");
        
        const formData = new FormData();
        formData.append('session_id', currentSessionId);
        formData.append('message', msg);

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            
            if (data.status === 'success') {
                appendMessage('AI Reviewer', data.html_response, 'ai');
            } else {
                appendMessage('System Error', data.message || 'Chat failed.', 'system');
            }
        } catch (err) {
            appendMessage('System Error', err.message, 'system');
        } finally {
            setStatus(true, "Ready");
        }
    });

    // Enter key support for textarea
    chatInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event('submit'));
        }
    });
});
