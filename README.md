# Nailivic Studios
Inventory management and production tracking webapp

## How to Edit Locally
### Setup SSH
Follow the instructions for [GitHub SSH](https://docs.github.com/en/authentication/connecting-to-github-with-ssh) to setup public and private keys, then confirm you're connected to the repo.

### Dowload the repo to your local machine
- go to https://github.com/turkosaurus/nailivic
- click on `Code` and either:
    - open with GitHub desktop
    - copy `git@github.com:Turkosaurus/nailivic.git`
- ensure that the repo is copied locally, either by following desktop prompts, or by entering on the command line `git@github.com:Turkosaurus/nailivic.git`

### Setup the local environment with `.env` file
This file contains all the secrets, including database connections and authorized user lists, which are stored as local environment variables that the app can access during execution.

### Install dependencies
`$ pip install -r requirements.txt`

### Run the application
From the shell, enter `flask run`, then open the link to view the page.

---

## Product Specifications:
- Laser Production Dashboard
- Parts Inventory (list and form)
- Product Inventory (list and form)
    - updated from Square
- Shipping Dashboard
    - updated from Shopify

## Description
To capture, calculate, and display all data pertaining to producing laser cut wooden art pieces en mass for Nailivic Studios.

### How It Works
Build the parts laser queue from projections:

1. Total a given event's target production
2. Subtract matching items already in inventory
3. Determine parts needed for remaining total
4. Subtract parts already in inventory
5. Store remaining totals into laser queue
6. Also add corresponding backs and boxes

Producing parts and making items and boxes updates the laser production queue in real time.


### How to Use
- Parts: Add to, remove from, or view inventory of laser etched parts
- Items: Add to, remove from, or view inventory of assembled items 
- Projections: Enter the number of completed items necessary for the upcoming Production Cycle (todo: capture from square)
<!-- - Shipping: #TODO (todo: update from shopify) -->
- Dashboard (home): display the current total number of parts onhand, and parts required to meet production goals, sorted

> Production Cycle: period of time or event before which all production needs should be met

> While the Production Cycle can be changed to compare against different targets, those targets will always be compared against the same "on hand" inventory values.

> Each part has 2-3 colors, and backs. The backs are together considered on of the part "colors"

# Development Tasks

## Unscheduled
#### accessibility
- complete checklist
#### automate
- alerts and logging
- test backups and alerts


# Version History

## v1.2.1 (in development)
- bugfix: 2-color items
- design improvements

## v1.2.0
- added items queue
- added scroll memory for long /items and /projections pages

## v1.1.0
- migrated all database queries to `psycopg2` for performance
- modularized code with `helpers.py`, and `database.py`
- added seperate test data and procedures

## v1.0.0
- progress bars for production objectives 
- custom dark style from modified bootstrap

## v0.9.0
- dedicated parts routes by color
- make button directly from part size/name table

## v0.8.0
- csv projection exports & imports
- parts and items inventory export

## v0.7.0
- SKU number system

## v0.6.0
- used box inventory routes added
- title tips for option menus

## v0.5.0
- deplete parts when items are produced
- build totals table to include backs and boxes
- adjust production table when part is made
- adjust production table when item is made

## v0.4.0
- built csv import to database
- refined formatting on entry forms
- wrote box and backs inventory and production logic
- rewrote production building function
- complete data restructuring (86 loterias SUB newloterias)

## v0.3.0
- setup sort columns and categories for
    - items
    - parts
    - projections
    - shipping
    - dashboard
- build production database
    - take projections
    - subtract on hand
    - queue what's needed for production

## v0.2.0
- setup form capture items into database
- setup form to caputre parts into database
- setup form to capture production target
    - change cycle feature
    - create new cycle page
    - associate each projection with a cycle

## v0.1.0
- buildout online hello nailivic in flask
- get squareup credentials
- get shopify credentials
- confirm main routes
- setup register and login
- design db structure
