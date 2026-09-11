#Requires AutoHotkey v2.0
#SingleInstance Force

; 設定儲存的檔案路徑，預設與此腳本放在同一個資料夾
saveFile := A_ScriptDir "\待下載.txt"

; 註冊剪貼簿變更事件監聽器
OnClipboardChange ClipChanged

ClipChanged(Type) {
    ; Type = 1 代表剪貼簿中是純文字
    if (Type = 1) {
        clipText := A_Clipboard
        
        ; 使用正規表達式匹配包含 eyny.com 的網址
        if (RegExMatch(clipText, "i)https?://\S*eyny\.com\S*", &match)) {
            url := Trim(match[0])
            url := RegExReplace(url, "[。，,;；'""`(\)\[\]\{\}<>、]+$", "")
            
            ; 檢查該網址是否已經記錄過，避免重複寫入
            alreadyExists := false
            if FileExist(saveFile) {
                try {
                    Loop read, saveFile {
                        line := Trim(A_LoopReadLine)
                        if (line = url) {
                            alreadyExists := true
                            break
                        }
                    }
                }
            }
            
            ; 如果檔案中還沒有這個網址，就追加寫入
            if (!alreadyExists) {
                try {
                    prefix := ""
                    if (FileExist(saveFile) && FileGetSize(saveFile) > 0) {
                        content := FileRead(saveFile, "UTF-8")
                        if (content != "" && SubStr(content, -1) != "`n") {
                            prefix := "`n"
                        }
                    }
                    FileAppend(prefix url "`n", saveFile, "UTF-8")
                    ; 在系統右下角顯示通知提示
                    TrayTip "已自動記錄伊莉網址至待下載.txt", url, 1
                } catch Error as err {
                    MsgBox "寫入檔案失敗: " err.Message, "錯誤", 16
                }
            }
        }
    }
}
