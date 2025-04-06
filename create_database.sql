\c online_shop

create table customers (
    id serial primary key,
    email varchar(100),
    password varchar(50),
    role varchar(10),
    session_id varchar(20)
);

create table products (
    id serial primary key,
    name varchar(50) not Null,
    description text,
    price decimal(10, 2),
    quantity int
    access boolean
);

create table orders (
    id serial primary key,
    customer_id int references customers(id),
    order_date timestamp default current_timestamp
);

create table order_details (
    id serial primary key,
    order_id int references orders(id),
    product_id int references products(id),
    quantity int check (Quantity > 0)
);
