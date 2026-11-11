/** 统一主题/分组词表：聊天页（会话主题）与记忆页（事实分组）共用，避免两页命名不一致。 */

export const TOPIC = {
  swim: "游泳记录",
  ball: "球类运动",
  run: "跑步记录",
  fitness: "健身记录",
  health: "身体数据",
  model: "模型与配置",
  game: "游戏",
  memory: "记忆写入",
  chat: "闲聊",
  diet: "饮食偏好",
  pet: "宠物",
  travel: "旅行",
  trip: "出差",
  work: "工作",
  other: "其他",
} as const;

/** 由任意文本（会话标题/事实内容）推断规范主题。 */
export function topicOfText(text: string): string {
  const s = text.toLowerCase();
  if (/游泳|泳池|自由泳|蛙泳|蝶泳|仰泳|swim/.test(s)) return TOPIC.swim;
  if (/乒乓球|羽毛球|网球|篮球|足球|排球|台球|球类/.test(s)) return TOPIC.ball;
  if (/5k|跑步|晨跑|夜跑|赛跑|配速|半马|全马|\bpb\b/.test(s)) return TOPIC.run;
  if (/健身|骑行|瑜伽|增肌|力量训练/.test(s)) return TOPIC.fitness;
  if (/体重|身高|体脂|睡眠|心率|health/.test(s)) return TOPIC.health;
  if (/模型|model|大模型|大肥鱼|deepseek|minimax/i.test(s)) return TOPIC.model;
  if (/游戏|遗器|太空封印|崩铁|星穹|原神|绝区零|抽卡|角色|技能|副本|深渊|配队/.test(s)) return TOPIC.game;
  if (/饮食|米饭|咖啡|早餐|午餐|晚餐|口味|爱吃|喜欢吃|吃饭|吃素|吃肉|食物|食谱/.test(s)) return TOPIC.diet;
  if (/宠物|猫|狗|豆豆|仓鼠|鹦鹉|兔子/.test(s)) return TOPIC.pet;
  if (/旅行|旅游|云南|大理|丽江|景点/.test(s)) return TOPIC.travel;
  if (/出差|成都|会议/.test(s)) return TOPIC.trip;
  if (/工作|项目|开发|实现|anchorline|lorekeeper/.test(s)) return TOPIC.work;
  if (/记住|记忆|存下|保存|归档/.test(s)) return TOPIC.memory;
  if (/你好|hi|hello|在吗|闲聊/.test(s)) return TOPIC.chat;
  return TOPIC.other;
}

const CANON: [RegExp, string][] = [
  [/^饮食/, TOPIC.diet],
  [/^跑步|^5k/i, TOPIC.run],
  [/^游泳/, TOPIC.swim],
  [/^乒乓|^球类/, TOPIC.ball],
  [/^健身/, TOPIC.fitness],
  [/^身体/, TOPIC.health],
  [/^模型|^配置/, TOPIC.model],
  [/^游戏|^遗器|^太空|^崩铁|^原神|^绝区零/, TOPIC.game],
  [/^宠物|^猫|^狗/, TOPIC.pet],
  [/^旅行/, TOPIC.travel],
  [/^出差/, TOPIC.trip],
  [/^工作|^项目/, TOPIC.work],
  [/^记忆/, TOPIC.memory],
  [/^闲聊/, TOPIC.chat],
  [/^其他|^其它/, TOPIC.other],
];

/** 把模型生成或历史遗留的 topic 归一到统一词表。 */
export function canonicalTopic(topic: string): string {
  const t = (topic || "").trim();
  if (!t) return TOPIC.other;
  // 大模型/大肥鱼/DeepSeek 相关一律归「模型与配置」，优先于「饮食」等关键词
  if (/大肥鱼|大模型|deepseek|minimax/i.test(t)) return TOPIC.model;
  for (const [re, name] of CANON) if (re.test(t)) return name;
  return topicOfText(t);
}
