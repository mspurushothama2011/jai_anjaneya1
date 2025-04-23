// Get user's timezone and store it in a cookie for server-side use
document.addEventListener('DOMContentLoaded', function() {
    try {
        // Use Intl.DateTimeFormat to get user's timezone
        const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
        console.log("Detected user timezone:", timezone);
        
        // Store timezone in localStorage
        localStorage.setItem('userTimezone', timezone);
        
        // Add timezone to all AJAX requests
        $(document).ajaxSend(function(e, xhr, options) {
            xhr.setRequestHeader('X-User-Timezone', timezone);
        });
        
        // Set a cookie with the timezone that the server can read
        document.cookie = `userTimezone=${timezone}; path=/; max-age=31536000; SameSite=Lax`;
        
        // Optionally send the timezone to the server right away
        fetch('/set-timezone', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-User-Timezone': timezone
            },
            body: JSON.stringify({ timezone: timezone })
        })
        .then(response => response.json())
        .then(data => console.log("Timezone set on server:", data))
        .catch(error => console.error("Error setting timezone:", error));
        
    } catch (error) {
        console.error("Error detecting timezone:", error);
    }
}); 