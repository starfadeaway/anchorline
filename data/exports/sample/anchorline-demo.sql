-- MySQL dump 10.13  Distrib 8.4.5, for Win64 (x86_64)
--
-- Host: 127.0.0.1    Database: anchorline_demo
-- ------------------------------------------------------
-- Server version	8.4.5

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `alembic_version`
--

DROP TABLE IF EXISTS `alembic_version`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `alembic_version` (
  `version_num` varchar(32) NOT NULL,
  PRIMARY KEY (`version_num`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Alembic 迁移版本（工具表，只存一行）';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `alembic_version`
--

LOCK TABLES `alembic_version` WRITE;
/*!40000 ALTER TABLE `alembic_version` DISABLE KEYS */;
INSERT INTO `alembic_version` VALUES ('0016');
/*!40000 ALTER TABLE `alembic_version` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `custom_skills`
--

DROP TABLE IF EXISTS `custom_skills`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `custom_skills` (
  `id` varchar(32) NOT NULL,
  `name` varchar(64) NOT NULL,
  `title` varchar(128) NOT NULL,
  `description` varchar(512) NOT NULL DEFAULT '',
  `instructions` text NOT NULL,
  `enabled` tinyint(1) NOT NULL DEFAULT '0',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `memory_entity` varchar(128) DEFAULT NULL,
  `auto_activate` tinyint(1) NOT NULL DEFAULT '0',
  `trigger_keywords` varchar(256) NOT NULL DEFAULT '',
  `negative_keywords` varchar(256) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  KEY `ix_custom_skills_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `custom_skills`
--

LOCK TABLES `custom_skills` WRITE;
/*!40000 ALTER TABLE `custom_skills` DISABLE KEYS */;
INSERT INTO `custom_skills` VALUES ('703fcb9519af46dbab8664e15e0b41f6','travel_plan','旅行规划','按记忆里的旅行计划给行程建议','用户问旅行/行程时，先检索记忆里的目的地、天数、预算；给出按天行程；不要编造未记录的偏好。',0,'2026-11-11 17:46:04','2026-11-11 17:54:03','user',0,'','');
/*!40000 ALTER TABLE `custom_skills` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `eval_runs`
--

DROP TABLE IF EXISTS `eval_runs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `eval_runs` (
  `id` varchar(32) NOT NULL,
  `benchmark` varchar(32) NOT NULL,
  `arm` varchar(16) NOT NULL,
  `budget_tokens` int NOT NULL,
  `question_id` varchar(64) NOT NULL,
  `score` float NOT NULL,
  `reader_model` varchar(128) NOT NULL,
  `judge_model` varchar(128) DEFAULT NULL,
  `judge_prompt_sha256` varchar(64) DEFAULT NULL,
  `config_hash` varchar(64) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `scoring_mode` varchar(16) NOT NULL DEFAULT 'deterministic',
  PRIMARY KEY (`id`),
  KEY `ix_eval_runs_question_id` (`question_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='评测结果：臂 × 题 × 预算的逐题得分';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `eval_runs`
--

LOCK TABLES `eval_runs` WRITE;
/*!40000 ALTER TABLE `eval_runs` DISABLE KEYS */;
/*!40000 ALTER TABLE `eval_runs` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `facts`
--

DROP TABLE IF EXISTS `facts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `facts` (
  `id` varchar(32) NOT NULL,
  `entity_id` varchar(128) NOT NULL,
  `attribute` varchar(128) NOT NULL,
  `value` text NOT NULL,
  `valid_from` datetime NOT NULL,
  `valid_to` datetime DEFAULT NULL,
  `source_session_id` varchar(128) DEFAULT NULL,
  `source_message_id` int DEFAULT NULL,
  `confidence` float NOT NULL DEFAULT '1',
  `supersedes_id` varchar(32) DEFAULT NULL,
  `fact_type` varchar(32) NOT NULL DEFAULT 'semantic',
  `conflict_type` varchar(32) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `skill_name` varchar(64) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_fact_entity_attr_from` (`entity_id`,`attribute`,`valid_from`),
  KEY `supersedes_id` (`supersedes_id`),
  KEY `ix_facts_entity_id` (`entity_id`),
  KEY `ix_facts_attribute` (`attribute`),
  KEY `ix_fact_lookup` (`entity_id`,`attribute`),
  CONSTRAINT `facts_ibfk_1` FOREIGN KEY (`supersedes_id`) REFERENCES `facts` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='事实记忆：实体/属性/值/生效时间；历史不物理删除（valid_to 标记失效）';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `facts`
--

LOCK TABLES `facts` WRITE;
/*!40000 ALTER TABLE `facts` DISABLE KEYS */;
INSERT INTO `facts` VALUES ('09c7a7410eb4438d929c47fc46ed68f4','user:demo','工作项目','LoreKeeper 知识库桥接','2026-10-27 17:07:22',NULL,'3af566feecf84774baee3569f9377335',NULL,1,'3282300ece214514a673d34c6d05f7ba','semantic',NULL,'2026-11-11 17:07:21',NULL),('0f97e5153b724335950576ea5a9ca712','user:demo','跑步 目标配速','5:00/km','2026-10-24 17:07:22','2026-11-11 17:07:22','9a23190e3ff647cca906d707bb292ee3',NULL,1,NULL,'semantic',NULL,'2026-11-11 17:07:21',NULL),('10e30e3691664c9bb71d987a01aaf7ff','user:demo','旅行计划','十一去云南','2026-11-01 17:07:22',NULL,'7cd97aa8e32747f3a75ddb50ee1825e5',NULL,1,NULL,'semantic',NULL,'2026-11-11 17:07:21',NULL),('3282300ece214514a673d34c6d05f7ba','user:demo','工作项目','Anchorline 记忆层','2026-07-14 17:07:22','2026-10-27 17:07:22','3af566feecf84774baee3569f9377335',NULL,1,NULL,'semantic',NULL,'2026-11-11 17:07:21',NULL),('47bb44f451d0451c881faed509348111','user:demo','200米游泳最好成绩','2分15秒','2026-09-12 17:07:22',NULL,'82206099100141e298bb91eee88de899',NULL,1,NULL,'semantic',NULL,'2026-11-11 17:07:21',NULL),('555794e1c80e4edfa75ffcf26f91c671','user:demo','咖啡习惯','每天两杯手冲','2026-10-22 17:07:22',NULL,'59e6356008e8428c980ba84792962e54',NULL,1,NULL,'semantic',NULL,'2026-11-11 17:07:21',NULL),('7b6a9fec9f864bbe800b38c07b337e71','user:demo','工作 目标','写完 M3 主实验','2026-11-08 17:07:22',NULL,'3af566feecf84774baee3569f9377335',NULL,1,NULL,'semantic',NULL,'2026-11-11 17:07:21',NULL),('7baf38f8f99e44f0bd8b34f7c20037ca','user:demo','5k_pb','23:50','2026-10-12 17:07:22',NULL,'9a23190e3ff647cca906d707bb292ee3',NULL,1,'acf3efb862244c708604317b57588b76','semantic',NULL,'2026-11-11 17:07:21',NULL),('9f8245be7ef449f9a258b8e297f91192','user:demo','饮食 偏好','清淡少油','2026-10-27 17:07:22','2026-11-11 17:07:22','59e6356008e8428c980ba84792962e54',NULL,1,NULL,'semantic',NULL,'2026-11-11 17:07:21',NULL),('a0628bcbcb6f44d48aed1efb8e669e49','user:demo','工作 项目','Anchorline 记忆层','2026-11-06 17:07:22',NULL,'3af566feecf84774baee3569f9377335',NULL,1,NULL,'semantic',NULL,'2026-11-11 17:07:21',NULL),('acb84186d62c4dd19ddc6c82acb47128','user:demo','跑步 配速','5:30/km','2026-10-22 17:07:22',NULL,'9a23190e3ff647cca906d707bb292ee3',NULL,1,NULL,'semantic',NULL,'2026-11-11 17:07:21',NULL),('acf3efb862244c708604317b57588b76','user:demo','5k_pb','24:30','2026-08-13 17:07:22','2026-10-12 17:07:22','9a23190e3ff647cca906d707bb292ee3',NULL,1,'b3c1c5d837864083b58680dcda776633','semantic',NULL,'2026-11-11 17:07:21',NULL),('b3c1c5d837864083b58680dcda776633','user:demo','5k_pb','27:12','2026-05-15 17:07:22','2026-08-13 17:07:22','9a23190e3ff647cca906d707bb292ee3',NULL,1,NULL,'semantic',NULL,'2026-11-11 17:07:21',NULL),('d0f3828b7b884c089cc7b57c2ae89df9','user:demo','饮食 禁忌','不吃辣','2026-10-29 17:07:22',NULL,'59e6356008e8428c980ba84792962e54',NULL,1,NULL,'semantic',NULL,'2026-11-11 17:07:21',NULL),('d370418252a7411791df77e82327946c','user:demo','饮食偏好','喜欢清淡，少油少盐','2026-10-12 17:07:22',NULL,'59e6356008e8428c980ba84792962e54',NULL,1,NULL,'semantic',NULL,'2026-11-11 17:07:21',NULL);
/*!40000 ALTER TABLE `facts` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `messages`
--

DROP TABLE IF EXISTS `messages`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `messages` (
  `id` int NOT NULL AUTO_INCREMENT,
  `session_id` varchar(32) NOT NULL,
  `role` varchar(16) NOT NULL,
  `content` text NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_messages_session_id` (`session_id`),
  CONSTRAINT `messages_ibfk_1` FOREIGN KEY (`session_id`) REFERENCES `sessions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=137 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='会话消息（user / assistant）';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `messages`
--

LOCK TABLES `messages` WRITE;
/*!40000 ALTER TABLE `messages` DISABLE KEYS */;
INSERT INTO `messages` VALUES (125,'9a23190e3ff647cca906d707bb292ee3','user','[demo] 我最近在练 5K，想突破 23 分钟','2026-11-11 17:07:21'),(127,'82206099100141e298bb91eee88de899','user','[demo] 我 200 米自由泳最好成绩是 2 分 15 秒','2026-11-11 17:07:21'),(129,'431774d91b794093befcd1b4c206f691','user','[demo] 我打乒乓球已经连胜 5 个对手了','2026-11-11 17:07:21'),(131,'59e6356008e8428c980ba84792962e54','user','[demo] 我口味清淡，少油少盐','2026-11-11 17:07:21'),(133,'3af566feecf84774baee3569f9377335','user','[demo] 我在做 Anchorline 记忆层这个项目','2026-11-11 17:07:21'),(135,'7cd97aa8e32747f3a75ddb50ee1825e5','user','[demo] 十一打算去云南玩','2026-11-11 17:07:21');
/*!40000 ALTER TABLE `messages` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `review_decisions`
--

DROP TABLE IF EXISTS `review_decisions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `review_decisions` (
  `id` varchar(32) NOT NULL,
  `entity_id` varchar(128) NOT NULL,
  `attribute` varchar(128) DEFAULT NULL,
  `kept_fact_id` varchar(32) NOT NULL,
  `invalidated_fact_ids` text NOT NULL,
  `reason` text,
  `operator` varchar(32) NOT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_review_decisions_entity_id` (`entity_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='人工裁决金标：保留/失效/原因/操作者';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `review_decisions`
--

LOCK TABLES `review_decisions` WRITE;
/*!40000 ALTER TABLE `review_decisions` DISABLE KEYS */;
/*!40000 ALTER TABLE `review_decisions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `sessions`
--

DROP TABLE IF EXISTS `sessions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sessions` (
  `id` varchar(32) NOT NULL,
  `domain` varchar(32) NOT NULL DEFAULT 'chat',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `topic` varchar(32) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='会话（聊天/评测）：标题、主题标签、创建时间';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `sessions`
--

LOCK TABLES `sessions` WRITE;
/*!40000 ALTER TABLE `sessions` DISABLE KEYS */;
INSERT INTO `sessions` VALUES ('3af566feecf84774baee3569f9377335','chat','2026-11-08 17:07:22','工作'),('431774d91b794093befcd1b4c206f691','chat','2026-11-08 17:07:22','乒乓球'),('59e6356008e8428c980ba84792962e54','chat','2026-11-08 17:07:22','饮食'),('7cd97aa8e32747f3a75ddb50ee1825e5','chat','2026-11-08 17:07:22','旅行'),('82206099100141e298bb91eee88de899','chat','2026-11-08 17:07:22','游泳'),('9a23190e3ff647cca906d707bb292ee3','chat','2026-11-08 17:07:22','跑步');
/*!40000 ALTER TABLE `sessions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `skill_toggles`
--

DROP TABLE IF EXISTS `skill_toggles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `skill_toggles` (
  `name` varchar(64) NOT NULL,
  `enabled` tinyint(1) NOT NULL DEFAULT '0',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `memory_entity` varchar(128) DEFAULT NULL,
  `auto_activate` tinyint(1) NOT NULL DEFAULT '0',
  `trigger_keywords` varchar(256) NOT NULL DEFAULT '',
  `description` text,
  `instructions` text,
  `negative_keywords` varchar(256) DEFAULT NULL,
  PRIMARY KEY (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `skill_toggles`
--

LOCK TABLES `skill_toggles` WRITE;
/*!40000 ALTER TABLE `skill_toggles` DISABLE KEYS */;
INSERT INTO `skill_toggles` VALUES ('run_coach',1,'2026-11-11 18:11:03','user',1,'',NULL,NULL,NULL);
/*!40000 ALTER TABLE `skill_toggles` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `traces`
--

DROP TABLE IF EXISTS `traces`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `traces` (
  `id` int NOT NULL AUTO_INCREMENT,
  `session_id` varchar(32) DEFAULT NULL,
  `query` text NOT NULL,
  `budget_tokens` int NOT NULL,
  `used_tokens` int NOT NULL,
  `layers` varchar(64) NOT NULL,
  `injected_fact_ids` text,
  `resolution` varchar(32) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `recalls` text,
  PRIMARY KEY (`id`),
  KEY `ix_traces_session_id` (`session_id`)
) ENGINE=InnoDB AUTO_INCREMENT=285 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='检索/聊天轨迹：预算、注入事实、召回明细、终止原因';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `traces`
--

LOCK TABLES `traces` WRITE;
/*!40000 ALTER TABLE `traces` DISABLE KEYS */;
/*!40000 ALTER TABLE `traces` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping routines for database 'anchorline_demo'
--
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed
