# SmartGuard 手机 App 部署指南

通过 Capacitor 将 Web 应用打包成 Android/iOS 原生 App。

## 前提条件

- Node.js 18+
- Android Studio（Android 开发）
- （可选）Xcode（iOS 开发，需要 Mac）

---

## 第一步：安装 Capacitor

在 `agent/web` 目录执行：

```bash
npm install @capacitor/core @capacitor/cli @capacitor/android @capacitor/ios --save-dev
```

---

## 第二步：初始化 Capacitor

```bash
npx cap init SmartGuard com.smartguard.app --web-dir=dist
```

这会创建 `capacitor.config.ts` 文件。

---

## 第三步：添加 Android 平台

```bash
npx cap add android
```

---

## 第四步：构建 Web 应用

```bash
npm run build
```

这会生成 `dist` 文件夹。

---

## 第五步：同步到 Android 项目

```bash
npx cap sync android
```

---

## 第六步：在 Android Studio 中打包 APK

```bash
npx cap open android
```

1. Android Studio 打开后，等待 Gradle 同步完成
2. 点击 **Build > Generate Signed Bundle / APK**
3. 选择 **APK > Next**
4. 如果没有签名密钥，点击 "Create new" 创建一个：
   - Key store path: 选择保存位置
   - Password: 设置密码
   - Alias: 取个名字如 `smartguard`
   - 有效期: 25 年
5. 选择 release，点击 Finish
6. APK 会生成在 `app/release/output-metrics.txt` 或类似位置

---

## 第七步：安装到手机

将 APK 文件复制到手机，通过文件管理器安装。

---

## 第八步：配置 App 访问 ngrok

1. 打开 SmartGuard App
2. 进入 **设置** 页面
3. 在 **服务器配置** 部分点击 **修改**
4. 输入你的 ngrok 地址，例如：
   ```
   https://abc123.ngrok.io
   ```
5. 点击 **保存并重启**

App 会自动重新加载，连接到你的后端服务。

---

## 常见问题

### Q: 提示"应用需要安装未知来源应用"
- 在手机设置 > 安全 > 开启"允许未知来源"

### Q: API 连接失败
- 确保 ngrok 服务正在运行
- 检查输入的 ngrok 地址是否包含 `https://`
- 确认后端服务在 ngrok 启动前已经运行

### Q: 修改代码后如何更新 App？
```bash
npm run build
npx cap sync android
npx cap open android
```
然后重新打包 APK。

### Q: 如何打包 iOS？
```bash
npx cap add ios
npx cap sync ios
npx cap open ios
```
在 Xcode 中打包。

---

## API 地址配置说明

App 支持三种方式配置 API 地址（优先级从高到低）：

1. **手动设置（最高优先）**：用户通过设置页面手动配置，存储在 `localStorage`
2. **Capacitor 配置**：通过插件配置（高级用户）
3. **默认相对路径**：`/api/v1`（适用于同源部署）

这样可以灵活支持 ngrok、本地服务器、正式服务器等不同环境。
