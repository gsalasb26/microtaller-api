-- =============================================================================
-- add_foreign_keys.sql
-- Adds missing FK constraints to the microtaller database.
-- Safe to run multiple times: each block checks whether the constraint already
-- exists before trying to create it.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. vehicles.customer_id → customers.id
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM   information_schema.table_constraints tc
        JOIN   information_schema.key_column_usage   kcu
               ON  tc.constraint_name = kcu.constraint_name
               AND tc.table_schema    = kcu.table_schema
        WHERE  tc.constraint_type = 'FOREIGN KEY'
        AND    tc.table_name      = 'vehicles'
        AND    kcu.column_name    = 'customer_id'
    ) THEN
        ALTER TABLE vehicles
            ADD CONSTRAINT fk_vehicles_customer_id
            FOREIGN KEY (customer_id)
            REFERENCES customers (id)
            ON DELETE RESTRICT;

        RAISE NOTICE 'Created fk_vehicles_customer_id';
    ELSE
        RAISE NOTICE 'fk_vehicles_customer_id already exists, skipping';
    END IF;
END;
$$;

-- -----------------------------------------------------------------------------
-- 2. work_orders.vehicle_id → vehicles.id
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM   information_schema.table_constraints tc
        JOIN   information_schema.key_column_usage   kcu
               ON  tc.constraint_name = kcu.constraint_name
               AND tc.table_schema    = kcu.table_schema
        WHERE  tc.constraint_type = 'FOREIGN KEY'
        AND    tc.table_name      = 'work_orders'
        AND    kcu.column_name    = 'vehicle_id'
    ) THEN
        ALTER TABLE work_orders
            ADD CONSTRAINT fk_work_orders_vehicle_id
            FOREIGN KEY (vehicle_id)
            REFERENCES vehicles (id)
            ON DELETE RESTRICT;

        RAISE NOTICE 'Created fk_work_orders_vehicle_id';
    ELSE
        RAISE NOTICE 'fk_work_orders_vehicle_id already exists, skipping';
    END IF;
END;
$$;

-- -----------------------------------------------------------------------------
-- 3. work_order_items.work_order_id → work_orders.id
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM   information_schema.table_constraints tc
        JOIN   information_schema.key_column_usage   kcu
               ON  tc.constraint_name = kcu.constraint_name
               AND tc.table_schema    = kcu.table_schema
        WHERE  tc.constraint_type = 'FOREIGN KEY'
        AND    tc.table_name      = 'work_order_items'
        AND    kcu.column_name    = 'work_order_id'
    ) THEN
        ALTER TABLE work_order_items
            ADD CONSTRAINT fk_work_order_items_work_order_id
            FOREIGN KEY (work_order_id)
            REFERENCES work_orders (id)
            ON DELETE CASCADE;

        RAISE NOTICE 'Created fk_work_order_items_work_order_id';
    ELSE
        RAISE NOTICE 'fk_work_order_items_work_order_id already exists, skipping';
    END IF;
END;
$$;

-- -----------------------------------------------------------------------------
-- 4. Verify — lists all FK constraints on the four tables
-- -----------------------------------------------------------------------------
SELECT
    tc.table_name,
    kcu.column_name,
    ccu.table_name  AS references_table,
    ccu.column_name AS references_column,
    rc.delete_rule
FROM information_schema.table_constraints        tc
JOIN information_schema.key_column_usage         kcu  ON tc.constraint_name = kcu.constraint_name
                                                      AND tc.table_schema    = kcu.table_schema
JOIN information_schema.referential_constraints  rc   ON tc.constraint_name = rc.constraint_name
JOIN information_schema.constraint_column_usage  ccu  ON rc.unique_constraint_name = ccu.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
AND   tc.table_name IN ('customers', 'vehicles', 'work_orders', 'work_order_items')
ORDER BY tc.table_name, kcu.column_name;

-- -----------------------------------------------------------------------------
-- 2.a work_orders.customer_id → customers.id
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM   information_schema.table_constraints tc
        JOIN   information_schema.key_column_usage   kcu
               ON  tc.constraint_name = kcu.constraint_name
               AND tc.table_schema    = kcu.table_schema
        WHERE  tc.constraint_type = 'FOREIGN KEY'
        AND    tc.table_name      = 'work_orders'
        AND    kcu.column_name    = 'customer_id'
    ) THEN
        ALTER TABLE work_orders
            ADD CONSTRAINT fk_work_orders_customer_id
            FOREIGN KEY (customer_id)
            REFERENCES customers (id)
            ON DELETE RESTRICT;

        RAISE NOTICE 'Created fk_work_orders_customer_id';
    ELSE
        RAISE NOTICE 'fk_work_orders_customer_id already exists, skipping';
    END IF;
END;
$$;
