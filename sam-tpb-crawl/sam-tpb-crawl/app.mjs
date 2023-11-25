import AWS from 'aws-sdk';
const ssm = new AWS.SSM({ region: 'us-east-2' });
let SCRAPER_API_KEY;

const assert = require('node:assert');
const { chromium, devices } = require('playwright');

export const lambdaHandler = async (event, context) => {
    try {
        if (!SCRAPER_API_KEY) {
            // console.log("Fetching SCRAPER_API_KEY from SSM...");
            const response = await ssm.getParameter({ Name: 'SCRAPER_API_KEY', WithDecryption: false }).promise();
            SCRAPER_API_KEY = response.Parameter.Value;
            // console.log("Fetched SCRAPER_API_KEY: ", !!SCRAPER_API_KEY);
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
