import { ApiHandler } from "sst/node/api";
import cheerio from "cheerio"
import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import {
  GetCommand,
  UpdateCommand,
  DynamoDBDocumentClient,
  PutCommand,
} from "@aws-sdk/lib-dynamodb";
import { Table } from "sst/node/table";


const buildSearchUrl = (songName: string, artistName: string) => {
    const fixedName = encodeURIComponent(artistName.replace("&", "%26"));
    const fixedSong = encodeURIComponent(songName.replace("&", "%26"));
    return `https://www.ultimate-guitar.com/search.php?title=${fixedName} ${fixedSong}&page=1&type=300`.replace(" ", "%20");
};

const getTabPageUrls = async (searchUrl: string) => {
    try {
        const response = await fetch(searchUrl);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const html = await response.text();
        const $ = cheerio.load(html);
        const dataContent = $('.js-store').attr('data-content');

        if (!dataContent) {
            return false
        }

        const pageData = JSON.parse(dataContent);
        const results = pageData.store.page.data.results;

        console.log(results)

        if (results.length !== 0) {
            return true
        }
    } catch (error) {
        console.error(`Error fetching tab page URLs: ${error}`);
        return false;
    }

    return false
};



export const handler = ApiHandler(async (evt) => {
    const { artist, song, spotifyId } = evt.queryStringParameters

    const db = DynamoDBDocumentClient.from(new DynamoDBClient({}));
    console.log(spotifyId)
    const get = new GetCommand({
        TableName: Table.Cache.tableName,
        Key: {
            "spotifyId": spotifyId
        }
    })

    const results = await db.send(get);
    console.log(results)
    if (results.Item) {
        return {
            statusCode: 200,
            body: true,
            headers: {
                'Cache-Control': "max-age=604800"
            }
        }
    }

    console.log(results)

    const url = buildSearchUrl(artist, song)
    const areTabs = await getTabPageUrls(url)

    if (!areTabs) {
        return {
            statusCode: 200,
            body: false,
            headers: {
                'Cache-Control': "max-age=604800"
            }
        }
    }

    const write = new PutCommand({
        TableName: Table.Cache.tableName,
        Item: {
            inUG: "",
            spotifyId: spotifyId
        }
    })

    await db.send(write)

    return {
        statusCode: 200,
        headers: {
            'Cache-Control': "max-age=604800"
        },
        body: areTabs,
    };
});