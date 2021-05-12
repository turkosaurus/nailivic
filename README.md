# Nailivic Studios
Inventory management and production tracking webapp

## Initial Specifications:
- Laser Production Dashboard
- Parts Inventory (list and form)
- Product Inventory (list and form)
    - updated from Square
- Shipping Dashboard
    - updated from Shopify

## Description
To capture, calculate, and display all data pertaining to producing laser cut wooden art pieces en mass for Nailivic Studios.

### How to Use
- Parts: Add to, remove from, or view inventory of laser etched parts
- Items: Add to, remove from, or view inventory of assembled items 
- Projections: Enter the number of completed items necessary for the upcoming Production Cycle (todo: capture from square)
- Shipping: #TODO (todo: update from shopify)
- Dashboard (home): display the current total number of parts onhand, and parts required to meet production goals, sorted

> Production Cycle: period of time or event before which all production needs should be met

> While the Production Cycle can be changed to compare against different targets, those targets will always be compared against the same "on hand" inventory values.

> Each part has 2-3 colors, and backs. The backs are together considered on of the part "colors"

# Development Tasks
## v0.4
- built csv import to database
- refined formatting on entry forms
- wrote box and backs inventory and production logic
- complete data restructuring (86 loterias SUB newloterias)

## Unscheduled
#### style
- custom dark mode
- monospace font
#### accessibility
- complete checklist
#### test and verify
- id and run tests
#### document
- standard uses
#### automate
- database backup and migration
- alerts and logging
- test backups and alerts

## Maybe
- route to produce csv of backup data
- csv or google forms inventory caputure

# Released Versions
## v0.1
- buildout online hello nailivic in flask
- get squareup credentials
- get shopify credentials
- confirm main routes
- setup register and login
- design db structure

## v0.2
- setup form capture items into database
- setup form to caputre parts into database
- setup form to capture production target
    - change cycle feature
    - create new cycle page
    - associate each projection with a cycle

## v0.3
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
