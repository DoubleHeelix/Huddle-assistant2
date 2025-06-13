# components/card.py

import streamlit as st
import re
import uuid
import streamlit.components.v1 as components

def render_polished_card(label, text_content, auto_copy=True):
    def format_text_html(text_to_format):
        cleaned_text = str(text_to_format).strip()
        normalized = re.sub(r"\n{2,}", "\n\n", cleaned_text)
        html_ready = normalized.replace('\n', '<br>')
        return re.sub(r"^(<br\s*/?>\s*)+", "", html_ready, flags=re.IGNORECASE | re.MULTILINE)

    safe_html_text_for_display = format_text_html(text_content)

    js_escaped_text_for_clipboard = str(text_content).replace("\\", "\\\\") \
                                                     .replace("`", "\\`") \
                                                     .replace('"', '\\"') \
                                                     .replace("\n", "\\n")

    card_instance_id = uuid.uuid4().hex[:8]
    unique_button_id = f"copy_btn_{card_instance_id}"
    unique_alert_id = f"copy_alert_{card_instance_id}"

    copy_button_html_structure = f"""
        <button id="{unique_button_id}"
                title="Copy to clipboard" class="copy-button">
            📋 Copy
        </button>
        <span id="{unique_alert_id}" class="copy-alert">
            Copied!
        </span>
    """

    st.markdown(
        f"""
    <div class="custom-card">
        <div class="card-header-h4">
            <span>✉️ {label}</span>
            <div class="button-container">{copy_button_html_structure}</div>
        </div>
        <div class="clear-both"></div>
        <div>{safe_html_text_for_display}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    script_to_run = f"""
    <script>
    (function() {{
        const textToCopy = `{js_escaped_text_for_clipboard}`;
        const copyButton = window.parent.document.getElementById('{unique_button_id}');
        const alertBox = window.parent.document.getElementById('{unique_alert_id}');

        function fallbackCopyTextToClipboard(text) {{
            const tempTextArea = document.createElement('textarea');
            tempTextArea.value = text;
            tempTextArea.style.position = 'absolute';
            tempTextArea.style.left = '-9999px';
            tempTextArea.style.top = '0';

            const doc = window.parent.document || document;
            doc.body.appendChild(tempTextArea);

            tempTextArea.focus();
            tempTextArea.select();

            let success = false;
            try {{
                success = doc.execCommand('copy');
                if (success) {{
                    alertBox.textContent = 'Copied!';
                    alertBox.style.color = '#90ee90';
                }} else {{
                    alertBox.textContent = 'Copy Failed';
                    alertBox.style.color = 'orange';
                }}
            }} catch (err) {{
                alertBox.textContent = 'Copy Error!';
                alertBox.style.color = 'red';
            }}

            alertBox.style.display = 'inline-block';
            setTimeout(() => {{ alertBox.style.display = 'none'; }}, success ? 1500 : 2500);
            doc.body.removeChild(tempTextArea);
        }}

        if (copyButton && alertBox) {{
            copyButton.onclick = function() {{
                if (navigator && navigator.clipboard && navigator.clipboard.writeText) {{
                    navigator.clipboard.writeText(textToCopy).then(() => {{
                        alertBox.textContent = 'Copied!';
                        alertBox.style.color = '#90ee90';
                        alertBox.style.display = 'inline-block';
                        setTimeout(() => {{ alertBox.style.display = 'none'; }}, 1500);
                    }}).catch(err => {{
                        fallbackCopyTextToClipboard(textToCopy);
                    }});
                }} else {{
                    fallbackCopyTextToClipboard(textToCopy);
                }}
            }};
        }}

        if ({str(auto_copy).lower()}) {{
            if (navigator && navigator.clipboard && navigator.clipboard.writeText) {{
                navigator.clipboard.writeText(textToCopy);
            }}
        }}
    }})();
    </script>
    """
    components.html(script_to_run, height=0)
