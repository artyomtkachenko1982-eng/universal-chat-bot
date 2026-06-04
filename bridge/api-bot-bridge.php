<?php
/**
 * api-bot-bridge.php — PHP-мостик для Universal Chat Bot
 *
 * Куда класть: в корень сайта turbinist.ru (рядом с index.php DLE)
 *
 * Что делает:
 * — Принимает POST-запросы от Python-бота
 * — Проверяет токен безопасности
 * — Вызывает функции DLE API
 * — Возвращает JSON-ответ
 *
 * Совместимость: PHP 7.1+ (на turbinist.ru стоит 7.1.33)
 */

// --------------------------------------------------
// 1. Заголовки
// --------------------------------------------------
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization');

// Preflight (браузерные OPTIONS-запросы)
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

// Только POST
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode([
        'success' => false,
        'message' => 'Только POST-запросы разрешены',
    ], JSON_UNESCAPED_UNICODE);
    exit;
}

// --------------------------------------------------
// 2. Читаем тело запроса
// --------------------------------------------------
$rawBody = file_get_contents('php://input');
$data = json_decode($rawBody, true);

if (!$data) {
    echo json_encode([
        'success' => false,
        'message' => 'Невалидный JSON',
    ], JSON_UNESCAPED_UNICODE);
    exit;
}

// --------------------------------------------------
// 3. Секретный токен (должен совпадать с .env на боте!)
// --------------------------------------------------
$SECRET_TOKEN = 'YzJkZDg4NWMtOGNiZi00OWYyLWE2YmYtM2RlMmU2YzgzMmI2MmMzNGI1NWEtMDFjYi00NzBlLWJmNDAtMzMzZThmNzYwNzQ2';

// Токен из заголовка Authorization: Bearer <token>
$authHeader = '';
if (isset($_SERVER['HTTP_AUTHORIZATION'])) {
    $authHeader = $_SERVER['HTTP_AUTHORIZATION'];
} elseif (isset($_SERVER['REDIRECT_HTTP_AUTHORIZATION'])) {
    // LiteSpeed может переименовать заголовок
    $authHeader = $_SERVER['REDIRECT_HTTP_AUTHORIZATION'];
}

$clientToken = '';
if (preg_match('/Bearer\s+(.+)/', $authHeader, $matches)) {
    $clientToken = $matches[1];
}

// Также проверяем токен из тела запроса (запасной вариант)
if (empty($clientToken) && isset($data['token'])) {
    $clientToken = $data['token'];
}

if ($clientToken !== $SECRET_TOKEN) {
    echo json_encode([
        'success' => false,
        'message' => 'Неверный токен авторизации',
    ], JSON_UNESCAPED_UNICODE);
    exit;
}

// --------------------------------------------------
// 4. Подключаем DLE API
// --------------------------------------------------
$dleApiPath = __DIR__ . '/engine/api/api.class.php';

if (!file_exists($dleApiPath)) {
    echo json_encode([
        'success' => false,
        'message' => 'DLE API не найден. Убедись, что мостик лежит в корне сайта.',
    ], JSON_UNESCAPED_UNICODE);
    exit;
}

require_once $dleApiPath;

// $dle_api уже создаётся внутри api.class.php автоматически.
// Никаких new DLEApi() не нужно — используем готовый объект.
if (!isset($dle_api)) {
    echo json_encode([
        'success' => false,
        'message' => 'DLE API не загрузился. Проверь версию DLE.',
    ], JSON_UNESCAPED_UNICODE);
    exit;
}

// --------------------------------------------------
// 5. Группы пользователей (ID → Название)
// --------------------------------------------------
$GROUP_NAMES = [
    1 => 'Начальники сайта',
    2 => 'Главные инженеры',
    3 => 'Инженеры',
    4 => 'Работники',
    5 => 'Безработные',
    6 => 'Временщики',
    7 => 'Премиум',
    8 => 'VIP',
    9 => 'Тестовая',
];

// --------------------------------------------------
// 6. Список разрешённых действий
// --------------------------------------------------
$action = isset($data['action']) ? $data['action'] : '';
$params = isset($data['params']) ? $data['params'] : [];

// Какие функции API можно вызывать через мостик
$allowedActions = [
    'external_auth',
    'take_user_by_name',
    'take_user_by_email',
    'take_user_by_id',
    'take_news',
    'take_users_by_group',
    'send_pm_to_user',
    'load_table',
    'change_user_group',
    'checkGroup',
    'external_register',
];

if (!in_array($action, $allowedActions)) {
    echo json_encode([
        'success' => false,
        'message' => "Действие '{$action}' не разрешено",
    ], JSON_UNESCAPED_UNICODE);
    exit;
}

// --------------------------------------------------
// 7. Выполняем действие
// --------------------------------------------------
try {
    $result = call_user_func_array([$dle_api, $action], $params);

    // Дополняем результат: добавляем group_name к данным пользователей
    $result = _enrich_with_group_names($result);

    echo json_encode([
        'success' => true,
        'action' => $action,
        'data' => $result,
    ], JSON_UNESCAPED_UNICODE);

} catch (Exception $e) {
    echo json_encode([
        'success' => false,
        'message' => 'Ошибка DLE API: ' . $e->getMessage(),
    ], JSON_UNESCAPED_UNICODE);
}

// --------------------------------------------------
// Функция: подставляет название группы по ID
// --------------------------------------------------
function _enrich_with_group_names($data) {
    global $GROUP_NAMES;

    // Это не массив — ничего не делаем
    if (!is_array($data)) {
        return $data;
    }

    // Одиночный пользователь (есть поле user_group)
    if (isset($data['user_group'])) {
        $gid = (int) $data['user_group'];
        $data['group_name'] = isset($GROUP_NAMES[$gid]) ? $GROUP_NAMES[$gid] : 'Группа #' . $gid;
        return $data;
    }

    // Список пользователей (take_users_by_group)
    if (isset($data[0]) && is_array($data[0]) && isset($data[0]['user_group'])) {
        foreach ($data as $i => $user) {
            $gid = (int) $user['user_group'];
            $data[$i]['group_name'] = isset($GROUP_NAMES[$gid]) ? $GROUP_NAMES[$gid] : 'Группа #' . $gid;
        }
    }

    return $data;
}
