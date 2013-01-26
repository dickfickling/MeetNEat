--drop table if exists sessions;
--drop table if exists locations;
--drop table if exists destinations;

create table if not exists sessions (
    sessionid long primary key,
    a_location integer,
    b_location integer,
    center_location integer,
    food_pref char[32]
);

create table if not exists locations (
    id integer primary key autoincrement,
    latitude integer,
    longitude integer
);

create table if not exists destinations (
    sessionid long,
    name char[32] not null,
    location integer not null,
    a_distance integer not null,
    b_distance integer not null,
    a_time integer not null,
    b_time integer not null
);

