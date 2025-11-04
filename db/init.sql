CREATE TABLE ventas (
  id SERIAL PRIMARY KEY,
  vendedor VARCHAR(50),
  sede VARCHAR(50),
  producto VARCHAR(100),
  cantidad INTEGER,
  precio NUMERIC,
  fecha DATE
);

COPY ventas(id, vendedor, sede, producto, cantidad, precio, fecha)
FROM '/docker-entrypoint-initdb.d/ventas.csv'
DELIMITER ','
CSV HEADER;