const fs = require('fs');
const qrcode = require('qrcode-terminal');
const { Client, LocalAuth, Poll } = require('whatsapp-web.js');

// Parse arguments
const args = process.argv.slice(2);
if (args.length === 0) {
    console.error("No input data provided.");
    process.exit(1);
}
const inputData = JSON.parse(fs.readFileSync(args[0], 'utf8'));
const chatName = inputData.chatName;
const slots = inputData.slots;

console.log(`Initializing WhatsApp Client...`);

function getBrowserPath() {
    const paths = [
        'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
        'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
        'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe'
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

    console.log('WhatsApp Client is logged in and ready! Syncing chats (waiting 5 seconds)...');
    try {
        await new Promise(r => setTimeout(r, 5000));

        const chats = await client.getChats();
        let targetChat = chats.find(c => c.name === chatName);

        if (!targetChat) {
            // Try fuzzy case-insensitive matching if exact match fails
            targetChat = chats.find(c => c.name && c.name.toLowerCase().trim() === chatName.toLowerCase().trim());
        }

        if (!targetChat) {
            // If still not found, try includes
            targetChat = chats.find(c => c.name && c.name.toLowerCase().includes(chatName.toLowerCase()));
        }

        if (!targetChat) {
            console.error(`\nERROR: Could not find a chat named "${chatName}".`);
            console.log("Here are the names of some recently active group chats to help you find the correct name:");
            const groups = chats.filter(c => c.isGroup);
            groups.slice(0, 15).forEach(c => console.log(`  - "${c.name}"`));

            await client.destroy();
            process.exit(1);
        }

        console.log(`Found chat "${targetChat.name}". Preparing to send polls...`);

        for (const [dateStr, options] of Object.entries(slots)) {
            if (options.length === 0) continue;

            // Limit to top 3 max options natively in the JS script
            const topOptions = options.slice(0, 3);
            const dateObj = new Date(dateStr);
            const formattedDate = dateObj.toLocaleDateString('en-GB', { weekday: 'long', day: '2-digit', month: '2-digit', year: 'numeric' });
            const pollTitle = `Padel Slots ${formattedDate}`;

            const pollOptions = topOptions.map(o => `${o.time} - ${o.price}`);

            console.log(`Sending poll: ${pollTitle}`);
            await targetChat.sendMessage(new Poll(pollTitle, pollOptions));

            // Wait a little between messages to avoid spam blocks
            await new Promise(r => setTimeout(r, 2000));
        }

        console.log('All polls successfully sent!');

    } catch (err) {
        console.error('Error sending polls:', err);
    }

    setTimeout(async () => {
        await client.destroy();
        process.exit(0);
    }, 3000);
});

client.initialize();
