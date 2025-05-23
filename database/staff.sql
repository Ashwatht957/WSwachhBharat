-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: May 08, 2025 at 11:32 AM
-- Server version: 10.4.32-MariaDB
-- PHP Version: 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `staff`
--

-- --------------------------------------------------------

--
-- Table structure for table `staff`
--

CREATE TABLE `staff` (
  `id` int(11) NOT NULL,
  `name` varchar(100) NOT NULL,
  `password` varchar(100) NOT NULL,
  `role` enum('worker','admin') NOT NULL,
  `ward_id` int(11) DEFAULT NULL,
  `EMAIL` varchar(255) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `staff`
--

INSERT INTO `staff` (`id`, `name`, `password`, `role`, `ward_id`, `EMAIL`) VALUES
(1, 'admin', 'admin123', 'admin', NULL, 'swachhindiamission@gmail.com'),
(13, 'ash', '123', 'admin', 9, 'prathamkoparde@gmail.com'),
(14, 'darshan', '123', 'worker', 11, 'prathamkoparde@gmail.com'),
(15, 'anku', '123', 'worker', 1, 'prathamkoparde@gmail.com'),
(17, 'Ashwath', '123', 'worker', 12, 'prathamkoparde@gmail.com'),
(20, 'cms', '123', 'worker', 19, 'prathamkoparde@gmail.com');

-- --------------------------------------------------------

--
-- Table structure for table `visited_links`
--

CREATE TABLE `visited_links` (
  `id` int(11) NOT NULL,
  `name` varchar(255) DEFAULT NULL,
  `latitude` float DEFAULT NULL,
  `longitude` float DEFAULT NULL,
  `ward_id` int(255) NOT NULL,
  `visited_at` datetime DEFAULT current_timestamp(),
  `EMAIL` varchar(255) NOT NULL,
  `image` longblob NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `visited_links`
--

INSERT INTO `visited_links` (`id`, `name`, `latitude`, `longitude`, `ward_id`, `visited_at`, `EMAIL`, `image`) VALUES
(1, 'John Doe', 28.6139, 77.209, 11, '2025-04-18 12:39:36', '', ''),
(6, 'sagarmal', 18.5245, 73.8527, 11, '2025-04-29 11:20:20', '', '');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `staff`
--
ALTER TABLE `staff`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `name` (`name`);

--
-- Indexes for table `visited_links`
--
ALTER TABLE `visited_links`
  ADD PRIMARY KEY (`id`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `staff`
--
ALTER TABLE `staff`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=21;

--
-- AUTO_INCREMENT for table `visited_links`
--
ALTER TABLE `visited_links`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=10;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
