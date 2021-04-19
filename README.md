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

### Menus
- Parts: Add to, remove from, or view inventory of laser etched parts
- Items: Add to, remove from, or view inventory of assembled items 
- Projections: Enter the number of completed items necessary for the upcoming Production Cycle (todo: capture from square)
- Shipping: #TODO (todo: update from shopify)
- Dashboard (home): display the current total number of parts required to meet production goals, sorted by color

> Production Cycle: period of time or event before which all production needs should be met

# Upcoming
## v0.2
- setup form capture items into database
- setup form to caputre parts into database
- ***CURRENT***
- setup form to capture production target
    - table contains:
        - cycle # | created date | description
        - new cycle / cycle selector

## v0.3
- setup sort columns and categories for
    - items
    - parts
    - projections
    - shipping
    - dashboard


## Unscheduled
#### style
- custom dark mode
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

# Released
## v0.1
- buildout online hello nailivic in flask
- get squareup credentials
- get shopify credentials
- confirm main routes
- setup register and login
- design db structure