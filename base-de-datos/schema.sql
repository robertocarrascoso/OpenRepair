CREATE DATABASE IF NOT EXISTS repairhub
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_general_ci;

USE repairhub;

-- Tabla de usuarios (login)
CREATE TABLE usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    rol ENUM('admin', 'tecnico') NOT NULL DEFAULT 'tecnico',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de los clientes
CREATE TABLE clientes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    telefono VARCHAR(20),
    email VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de las reparaciones
CREATE TABLE reparaciones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(20) NOT NULL UNIQUE,
    cliente_id INT NOT NULL,
    tipo_dispositivo VARCHAR(50) NOT NULL,
    marca VARCHAR(50),
    modelo VARCHAR(50),
    averia TEXT NOT NULL,
    observaciones TEXT,
    estado VARCHAR(30) DEFAULT 'Recibido',
    presupuesto DECIMAL(8,2),
    precio_final DECIMAL(8,2),
    presupuesto_aceptado BOOLEAN DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (cliente_id) REFERENCES clientes(id)
);

-- Contador de reparaciones por año (nunca retrocede)
CREATE TABLE contadores (
    year INT PRIMARY KEY,
    ultimo_num INT NOT NULL DEFAULT 0
);

-- Tabla del historial de estados
CREATE TABLE historial_estados (
    id INT AUTO_INCREMENT PRIMARY KEY,
    reparacion_id INT NOT NULL,
    estado VARCHAR(30) NOT NULL,
    tecnico VARCHAR(50),
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (reparacion_id) REFERENCES reparaciones(id)
);
