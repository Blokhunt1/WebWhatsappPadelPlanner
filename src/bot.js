const fs = require('fs');
const { exec } = require('child_process');
const qrcode = require('qrcode-terminal');
const { Client, LocalAuth, Poll } = require('whatsapp-web.js');
const path = require('path');

function getBrowserPath() {
    const paths = [
        'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
        'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
        'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
        '/usr/bin/google-chrome',
        '/usr/bin/chromium',
        '/usr/bin/chromium-browser'
    ];
    for (const p of paths) {
        if (fs.existsSync(p)) return p;
    }
    return null;
}

const client = new Client({
    authStrategy: new LocalAuth({ dataPath: './whatsapp_auth' }),
    puppeteer: {
        headless: true, // Run invisibly
        executablePath: getBrowserPath(),
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu']
    },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
});

client.on('qr', (qr) => {
    console.log('\n=========================================');
    console.log('SCAN THIS QR CODE WITH YOUR WHATSAPP APP');
    console.log('=========================================\n');
    qrcode.generate(qr, { small: true });
});

client.on('ready', async () => {
    if (client.__readyHandled) return;
    client.__readyHandled = true;
    console.log('\n✅ WhatsApp Bot is logged in and ready!');
    console.log('Listening for "?PADEL" or "?PADEL [days]" commands in any chat...\n');
});

client.on('message_create', async msg => {
    // Ignore if it's an automated reply from the bot itself (to prevent infinite loops)
    if (msg.fromMe && msg.body.includes('Generating Peakz Padel options')) return;
    if (msg.fromMe && msg.pollName) return;

    const text = msg.body.trim().toUpperCase();

    if (text.startsWith('?PADEL')) {
        let days = 4; // Default to 4 days
        const parts = text.split(' ');
        if (parts.length > 1 && !isNaN(parseInt(parts[1]))) {
            days = parseInt(parts[1]);
        }

        console.log(`[${new Date().toLocaleTimeString()}] Received command: "${msg.body}" from chat. Scanning for ${days} days...`);
        msg.reply(`🎾 Generating Peakz Padel options for the next ${days} days... This may take a minute 🎾`);

        // Find python executable assuming common structures
        let executable = 'python3'; // Default on Linux/Docker
        const venvPathWin = path.join(__dirname, '..', 'venv', 'Scripts', 'python.exe');
        const venvPathLin = path.join(__dirname, '..', 'venv', 'bin', 'python');

        if (fs.existsSync(venvPathWin)) {
            executable = venvPathWin;
        } else if (fs.existsSync(venvPathLin)) {
            executable = venvPathLin;
        } else {
            // Fallback for Windows if not in venv
            try { if (fs.existsSync('C:\\Python313\\python.exe')) executable = 'python'; } catch (e) { }
        }

        const scraperScript = path.join(__dirname, 'scraper.py');

        exec(`"${executable}" "${scraperScript}" --days ${days}`, { cwd: __dirname }, async (error, stdout, stderr) => {
            if (error) {
                console.error(`exec error: ${error}`);
                msg.reply(`❌ Error scraping padel slots: ${error.message}`);
                return;
            }

            try {
                // The JSON is always the absolute last line printed to stdout
                const lines = stdout.trim().split('\n');
                const jsonStr = lines[lines.length - 1];
                const slotsData = JSON.parse(jsonStr);

                const daysAvailable = Object.keys(slotsData);

                if (daysAvailable.length === 0) {
                    msg.reply("No padel slots found matching the criteria in that date range.");
                    return;
                }

                // Smart select up to 12 options 
                // Distribute evenly across days, and within days aim for Morning, Midday, Evening spread.
                const dayPools = [];
                for (const dateStr of daysAvailable) {
                    const daySlots = slotsData[dateStr];
                    if (!daySlots || daySlots.length === 0) continue;

                    const dateObj = new Date(dateStr);
                    // Generate format like "Mon 23/02"
                    const dayName = dateObj.toLocaleDateString('en-GB', { weekday: 'short', day: '2-digit', month: '2-digit' });

                    const morning = [];
                    const midday = [];
                    const evening = [];

                    for (const slot of daySlots) {
                        const hour = parseInt(slot.time.split(':')[0]);
                        const btnText = `${dayName} ${slot.time} (${slot.price})`;
                        const sortTime = new Date(dateStr + 'T' + slot.time + ':00');
                        const item = { text: btnText, time: sortTime };

                        if (hour < 12) morning.push(item);
                        else if (hour < 17) midday.push(item);
                        else evening.push(item);
                    }
                    dayPools.push({ morning, midday, evening, lastPicked: -1 });
                }

                const selectedSlots = [];
                let i = 0;

                // Keep round-robin picking until we have 12 slots or are completely out of options
                while (selectedSlots.length < 12 && dayPools.some(p => p.morning.length || p.midday.length || p.evening.length)) {
                    const pool = dayPools[i % dayPools.length];

                    let picked = null;
                    // Categories: 0:evening, 1:morning, 2:midday (this ensures an even spread across time of day)
                    for (let attempt = 1; attempt <= 3; attempt++) {
                        let cat = (pool.lastPicked + attempt) % 3;
                        if (cat === 0 && pool.evening.length > 0) { picked = pool.evening.shift(); pool.lastPicked = cat; break; }
                        if (cat === 1 && pool.morning.length > 0) { picked = pool.morning.shift(); pool.lastPicked = cat; break; }
                        if (cat === 2 && pool.midday.length > 0) { picked = pool.midday.shift(); pool.lastPicked = cat; break; }
                    }

                    if (picked) {
                        selectedSlots.push(picked);
                    }
                    i++;
                }

                // Sort chronologically so the poll is easily readable
                selectedSlots.sort((a, b) => a.time - b.time);

                const pollOptions = selectedSlots.map(s => s.text);
                if (pollOptions.length === 0) {
                    msg.reply("No padel slots found matching the criteria in that date range.");
                    return;
                }

                console.log(`Sending poll with ${pollOptions.length} options...`);
                // Send the WhatsApp Poll!
                await msg.reply(new Poll('🎾 Pick a Padel Slot! 🎾', pollOptions));

            } catch (err) {
                console.error("JSON parse or generation error", err);
                console.error("Stdout was:", stdout);
                msg.reply("❌ Error processing scraper results.");
            }
        });
    }
});

client.initialize();
