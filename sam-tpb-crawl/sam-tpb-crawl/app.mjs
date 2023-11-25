import playwright from 'playwright-aws-lambda';
import AWS from 'aws-sdk';
const ssm = new AWS.SSM({ region: 'us-east-2' });

let SCRAPER_API_KEY;

export const lambdaHandler = async (event, context) => {
    let browser = null;
    try {
        if (!SCRAPER_API_KEY) {
            const response = await ssm.getParameter({ Name: 'SCRAPER_API_KEY', WithDecryption: false }).promise();
            SCRAPER_API_KEY = response.Parameter.Value;
        }
        try {
            browser = await playwright.launchChromium();
            const context = await browser.newContext();
            const page = await context.newPage();
            await page.goto(event.url || `https://api.scraperapi.com/?api_key=${SCRAPER_API_KEY}&url=https://thepiratebay.org/search.php?q=top100:all`);
            console.log('Page title: ', await page.title());
        } catch (error) {
            throw error;
        } finally {
            if (browser) {
                await browser.close();
            }
        }

        const response = {
            'statusCode': 200,
            'body': JSON.stringify({
                message: "Good job",
            })
        };
        return response;
    } catch (err) {
        console.log(err);
        return err;
    }
};