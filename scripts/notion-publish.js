// Read all packages/**/notion_tasks.json and create pages in a Notion database.
const { Client } = require("@notionhq/client");
const fs = require("fs");
const glob = require("glob");

const notion = new Client({ auth: process.env.NOTION_TOKEN });
const databaseId = process.env.NOTION_DATABASE_ID;

(async () => {
  const files = glob.sync("packages/**/notion_tasks.json");
  for (const f of files) {
    const json = JSON.parse(fs.readFileSync(f, "utf8"));
    const pkg = f.split("/")[1]; // packages/<slug>/...

    for (const task of json.tasks || []) {
      await notion.pages.create({
        parent: { database_id: databaseId },
        properties: {
          Name: { title: [{ text: { content: task.summary } }] },
          Status: task.status ? { select: { name: task.status } } : undefined,
          Package: { rich_text: [{ text: { content: pkg } }] },
        },
        children: task.description
          ? [{ object: "block", paragraph: { rich_text: [{ text: { content: task.description } }] } }]
          : [],
      });
    }
  }
})();
