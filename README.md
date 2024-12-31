# FansDB community metadata scrapers

These community scrapers are tailored towards FansDB data structure. To use you need to have [stashapp/stash](https://github.com/stashapp/stash) application.

Source index: [`https://fansdb.github.io/metadata-scrapers/main/index.yml`](https://fansdb.github.io/metadata-scrapers/main/index.yml)

## Install 

1. To add a new source go to **Settings** > **Metadata Providers** page.
1. Under Available Scrapers click **Add Source**.
1. Add the following details:
    - Name: `FansDB`
    - Source URL: `https://fansdb.github.io/metadata-scrapers/main/index.yml`
    - Local path: `fansdb`
1. Click Confirm.
1. Under Available Scrapers select **FansDB** package to expand it and see all available scrapers.
1. Click the checkmark next to relevant scraper and click **Install**.

## Contributing

Pull requests are welcome.

### Repository structure

- Each scraper should have its own folder under [`/scrapers`](./scrapers).  
- Folder name should reflect the network name used in FansDB.

### Validation
The scrapers in this repository can be validated against a schema and checked for common errors.

First, install the validator's dependencies - inside the [`/validator`](./validator) folder, run: `yarn`.

Then, to run the validator, use `node validate.js` in the root of the repository.
Specific scrapers can be checked using: `node validate.js scrapers/folder/example.yml scrapers/folder2/example2.yml`

## Attributions

From [https://github.com/stashapp/CommunityScrapers](https://github.com/stashapp/CommunityScrapers) under AGPL-3.0:

- `./validate.js`
- `./build-site.sh`
- `./validator/*`
- `./.github/workflows/validate.yml`