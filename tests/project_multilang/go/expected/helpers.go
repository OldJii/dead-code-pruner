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
		false
	use(isOneWay)
}

func other() bool { return true }
func use(b bool) { println(b) }
