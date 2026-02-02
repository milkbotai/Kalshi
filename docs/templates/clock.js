/**
 * Binary Rogue Live Clock
 *
 * Displays current time in Eastern Time (EST/EDT)
 * with automatic DST detection.
 *
 * Usage:
 * 1. Add clock HTML to your page:
 *    <div class="br-clock" id="live-clock">
 *        <span class="br-clock-time">--:-- --</span>
 *        <span class="br-clock-tz">EST</span>
 *    </div>
 *
 * 2. Include this script at the bottom of your page
 */

(function() {
    'use strict';

    /**
     * Get the current timezone abbreviation for Eastern Time
     * @returns {string} 'EST' or 'EDT'
     */
    function getEasternTzAbbrev() {
        const now = new Date();
        const jan = new Date(now.getFullYear(), 0, 1);
        const jul = new Date(now.getFullYear(), 6, 1);

        // Get the standard time offset (larger offset = standard time)
        const stdOffset = Math.max(jan.getTimezoneOffset(), jul.getTimezoneOffset());

        // If current offset is less than standard, we're in DST
        const isDST = now.getTimezoneOffset() < stdOffset;

        return isDST ? 'EDT' : 'EST';
    }

    /**
     * Format the current time for display
     * @returns {string} Formatted time string (e.g., "3:45 PM")
     */
    function formatTime() {
        const now = new Date();
        const options = {
            hour: 'numeric',
            minute: '2-digit',
            hour12: true,
            timeZone: 'America/New_York'
        };
        return now.toLocaleTimeString('en-US', options);
    }

    /**
     * Update the clock display
     */
    function updateClock() {
        const clockTime = document.querySelector('.br-clock-time');
        const clockTz = document.querySelector('.br-clock-tz');

        if (clockTime) {
            clockTime.textContent = formatTime();
        }

        if (clockTz) {
            clockTz.textContent = getEasternTzAbbrev();
        }
    }

    /**
     * Initialize the clock
     */
    function init() {
        // Initial update
        updateClock();

        // Update every second
        setInterval(updateClock, 1000);
    }

    // Start when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
