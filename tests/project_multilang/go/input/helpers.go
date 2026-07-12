package demo

const INTL_FLAG = true // placeholder overwritten by pruner pattern

func deadUnexported() bool {
	return false
}

func LiveExported() {
	println("live")
}

func Multiline(flag bool) {
	isOneWay :=
		!INTL_FLAG &&
			flag &&
			other()
	use(isOneWay)
}

func other() bool { return true }
func use(b bool) { println(b) }
